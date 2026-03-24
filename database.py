"""
Модуль работы с SQLite базой данных.
"""

import json
import sqlite3
import logging
import time
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from config import Config
from fetchers.base_fetcher import Article

logger = logging.getLogger("sci_agent.database")


class Database:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Config.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self, timeout=10.0):
        """Возвращает соединение с таймаутом."""
        return sqlite3.connect(self.db_path, timeout=timeout)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    authors TEXT DEFAULT '',
                    abstract TEXT DEFAULT '',
                    doi TEXT,
                    url TEXT,
                    pdf_url TEXT,
                    pdf_path TEXT,
                    year INTEGER,
                    journal TEXT DEFAULT '',
                    keywords TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    language TEXT DEFAULT 'en',
                    summary_ru TEXT DEFAULT '',
                    abstract_ru TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url)
                );
                
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    sources TEXT DEFAULT '',
                    total_results INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS search_results (
                    search_id INTEGER,
                    article_id INTEGER,
                    relevance_rank INTEGER DEFAULT 0,
                    FOREIGN KEY (search_id) REFERENCES searches(id),
                    FOREIGN KEY (article_id) REFERENCES articles(id),
                    PRIMARY KEY (search_id, article_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
                CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
                CREATE INDEX IF NOT EXISTS idx_articles_year ON articles(year);
            """)
            logger.info(f"БД инициализирована: {self.db_path}")

    def save_article(self, article: Article) -> int:
        """Сохраняет статью (использует отдельное соединение)."""
        for attempt in range(3):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        INSERT INTO articles (
                            title, authors, abstract, doi, url, 
                            pdf_url, pdf_path, year, journal, keywords,
                            source, language, summary_ru, abstract_ru,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            title = excluded.title,
                            authors = excluded.authors,
                            abstract = excluded.abstract,
                            doi = excluded.doi,
                            pdf_url = excluded.pdf_url,
                            pdf_path = excluded.pdf_path,
                            year = excluded.year,
                            journal = excluded.journal,
                            keywords = excluded.keywords,
                            summary_ru = excluded.summary_ru,
                            abstract_ru = excluded.abstract_ru,
                            updated_at = excluded.updated_at
                    """, (
                        article.title,
                        json.dumps(article.authors, ensure_ascii=False),
                        article.abstract,
                        article.doi,
                        article.url,
                        article.pdf_url,
                        article.pdf_path,
                        article.year,
                        article.journal,
                        json.dumps(article.keywords, ensure_ascii=False),
                        article.source,
                        article.language,
                        article.summary_ru,
                        article.abstract_ru,
                        datetime.now().isoformat()
                    ))
                    return cursor.lastrowid
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    logger.warning(f"БД заблокирована, повторная попытка {attempt+1}/3")
                    time.sleep(1)
                    continue
                raise
        raise sqlite3.OperationalError("Не удалось сохранить статью после 3 попыток")

    def save_search(self, query: str, sources: List[str], articles: List[Article]) -> int:
        """
        Сохраняет поиск и все связанные статьи в одной транзакции.
        """
        with self._get_connection(timeout=15.0) as conn:
            # Сохраняем запрос
            cursor = conn.execute("""
                INSERT INTO searches (query, sources, total_results)
                VALUES (?, ?, ?)
            """, (query, json.dumps(sources), len(articles)))
            search_id = cursor.lastrowid

            # Сохраняем каждую статью в этой же транзакции
            for rank, article in enumerate(articles, 1):
                # Вставляем статью
                try:
                    cursor = conn.execute("""
                        INSERT INTO articles (
                            title, authors, abstract, doi, url, 
                            pdf_url, pdf_path, year, journal, keywords,
                            source, language, summary_ru, abstract_ru,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            title = excluded.title,
                            authors = excluded.authors,
                            abstract = excluded.abstract,
                            doi = excluded.doi,
                            pdf_url = excluded.pdf_url,
                            pdf_path = excluded.pdf_path,
                            year = excluded.year,
                            journal = excluded.journal,
                            keywords = excluded.keywords,
                            summary_ru = excluded.summary_ru,
                            abstract_ru = excluded.abstract_ru,
                            updated_at = excluded.updated_at
                    """, (
                        article.title,
                        json.dumps(article.authors, ensure_ascii=False),
                        article.abstract,
                        article.doi,
                        article.url,
                        article.pdf_url,
                        article.pdf_path,
                        article.year,
                        article.journal,
                        json.dumps(article.keywords, ensure_ascii=False),
                        article.source,
                        article.language,
                        article.summary_ru,
                        article.abstract_ru,
                        datetime.now().isoformat()
                    ))
                    article_id = cursor.lastrowid

                    # Связываем статью с поиском
                    conn.execute("""
                        INSERT OR IGNORE INTO search_results (search_id, article_id, relevance_rank)
                        VALUES (?, ?, ?)
                    """, (search_id, article_id, rank))
                except sqlite3.IntegrityError:
                    # Если статья уже существует, найдём её id
                    cur = conn.execute("SELECT id FROM articles WHERE url = ?", (article.url,))
                    row = cur.fetchone()
                    if row:
                        article_id = row[0]
                        conn.execute("""
                            INSERT OR IGNORE INTO search_results (search_id, article_id, relevance_rank)
                            VALUES (?, ?, ?)
                        """, (search_id, article_id, rank))

            conn.commit()
            logger.info(f"Поиск #{search_id} сохранён: {len(articles)} статей")
            return search_id

    def get_articles(self, source: str = None, year: int = None, limit: int = 100) -> List[dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM articles WHERE 1=1"
            params = []
            if source:
                query += " AND source = ?"
                params.append(source)
            if year:
                query += " AND year = ?"
                params.append(year)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> dict:
        with self._get_connection() as conn:
            stats = {}
            stats['total_articles'] = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            stats['by_source'] = {}
            for row in conn.execute("SELECT source, COUNT(*) FROM articles GROUP BY source"):
                stats['by_source'][row[0]] = row[1]
            stats['total_searches'] = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
            stats['with_doi'] = conn.execute("SELECT COUNT(*) FROM articles WHERE doi IS NOT NULL").fetchone()[0]
            stats['with_pdf'] = conn.execute("SELECT COUNT(*) FROM articles WHERE pdf_path IS NOT NULL").fetchone()[0]
            return stats