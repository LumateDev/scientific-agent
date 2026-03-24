"""
Модуль поиска статей в arXiv.org.

arXiv предоставляет бесплатный Atom API для поиска и получения
метаданных статей. Все статьи arXiv находятся в открытом доступе,
PDF всегда доступен для скачивания.

API документация: https://info.arxiv.org/help/api/index.html
"""

import re
import feedparser
from typing import List, Optional

from .base_fetcher import BaseFetcher, Article
from config import Config


class ArxivFetcher(BaseFetcher):
    """
    Получение статей из arXiv.org через Atom API.

    """

    def __init__(self):
        super().__init__("arxiv")
        self.base_url = Config.ARXIV_BASE_URL

    def is_available(self) -> bool:
        """arXiv всегда доступен (бесплатный API)."""
        return Config.ARXIV_ENABLED

    def _build_query(self, query: str) -> str:
        """
        Построение поискового запроса в формате arXiv API.
        
        arXiv поддерживает поиск по полям:
        - ti: заголовок
        - abs: аннотация
        - au: автор
        - all: все поля
        
        Пример: all:water AND all:dissociation
        """
        # Разбиваем запрос на термины
        terms = query.strip().split()

        # Строим запрос: ищем каждый термин во всех полях
        # Используем OR внутри группы синонимов и AND между группами
        query_parts = []
        for term in terms:
            # Экранируем специальные символы
            term = term.strip()
            if term and term.upper() not in ("AND", "OR", "NOT"):
                query_parts.append(f'all:"{term}"')

        # Объединяем через AND — все термины должны присутствовать
        arxiv_query = " AND ".join(query_parts)

        self.logger.debug(f"arXiv запрос: {arxiv_query}")
        return arxiv_query

    def _extract_doi(self, entry: dict) -> Optional[str]:
        """
        Извлечение DOI из записи arXiv.
        
        """
        # Прямой DOI
        doi = getattr(entry, 'arxiv_doi', None)
        if doi:
            return doi

        # Поиск в ссылках
        for link in entry.get('links', []):
            href = link.get('href', '')
            if 'doi.org' in href:
                # Извлекаем DOI из URL
                match = re.search(r'doi\.org/(.+)$', href)
                if match:
                    return match.group(1)

        return None

    def _extract_pdf_url(self, entry: dict) -> Optional[str]:
        """Извлечение ссылки на PDF из записи arXiv."""
        for link in entry.get('links', []):
            # PDF-ссылка имеет type="application/pdf"
            if link.get('type') == 'application/pdf':
                return link.get('href')
            # Или title="pdf"
            if link.get('title') == 'pdf':
                return link.get('href')

        arxiv_id = entry.get('id', '')
        if arxiv_id:
            # ID формата: http://arxiv.org/abs/2301.12345v1
            match = re.search(r'abs/(.+?)(?:v\d+)?$', arxiv_id)
            if match:
                return f"https://arxiv.org/pdf/{match.group(1)}.pdf"

        return None

    def _extract_year(self, entry: dict) -> Optional[int]:
        """Извлечение года публикации."""
        published = entry.get('published', '')
        if published:
            match = re.search(r'(\d{4})', published)
            if match:
                return int(match.group(1))
        return None

    def _extract_categories(self, entry: dict) -> List[str]:
        """Извлечение категорий/те��ов arXiv как ключевых слов."""
        tags = entry.get('tags', [])
        return [tag.get('term', '') for tag in tags if tag.get('term')]

    def _parse_entry(self, entry: dict) -> Article:
        """
        Преобразование записи Atom feed в объект Article.
        
        Args:
            entry: Запись из feedparser
            
        Returns:
            Объект Article с заполненными полями
        """
        # Авторы — список словарей с ключом 'name'
        authors = []
        for author in entry.get('authors', []):
            name = author.get('name', '').strip()
            if name:
                authors.append(name)

        # Чистим аннотацию от переносов строк
        abstract = entry.get('summary', '').strip()
        abstract = re.sub(r'\s+', ' ', abstract)

        # Заголовок
        title = entry.get('title', '').strip()
        title = re.sub(r'\s+', ' ', title)

        # Журнал (если статья опубликована)
        journal = getattr(entry, 'arxiv_journal_ref', '') or ''

        article = Article(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=self._extract_doi(entry),
            url=entry.get('id', ''),
            pdf_url=self._extract_pdf_url(entry),
            year=self._extract_year(entry),
            journal=journal if journal else "arXiv preprint",
            keywords=self._extract_categories(entry),
            source="arxiv",
            language="en",
            raw_data=dict(entry)
        )

        return article

    def search(self, query: str, max_results: int = None) -> List[Article]:
        """
        Поиск статей в arXiv.
        
        Args:
            query: Поисковый запрос (ключевые слова через пробел)
            max_results: Максимальное количество результатов
            
        Returns:
            Список найденных статей
        """
        if not self.is_available():
            self.logger.info("arXiv отключён в конфигурации")
            return []

        max_results = max_results or Config.MAX_RESULTS

        # Проверяем кэш
        cache_key = self._get_cache_key(query, max_results=max_results)
        cached = self._load_from_cache(cache_key)
        if cached:
            self.logger.info(
                f"Найдено {len(cached)} статей в кэше arXiv"
            )
            return [Article(**a) for a in cached]

        # Формируем запрос
        arxiv_query = self._build_query(query)

        params = {
            "search_query": arxiv_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }

        self.logger.info(
            f"Поиск в arXiv: '{query}' (макс. {max_results} результатов)"
        )

        # Выполняем запрос
        response = self._make_request(self.base_url, params=params)
        if not response:
            self.logger.error("Не удалось получить ответ от arXiv")
            return []

        # Парсим Atom feed
        feed = feedparser.parse(response.text)

        # Проверяем наличие результатов
        total_results = int(
            feed.feed.get('opensearch_totalresults', 0)
        )
        self.logger.info(f"arXiv: найдено {total_results} результатов")

        if not feed.entries:
            self.logger.warning("arXiv: нет записей в ответе")
            return []

        # Преобразуем записи в Article
        articles = []
        for entry in feed.entries:
            try:
                article = self._parse_entry(entry)
                articles.append(article)
                self.logger.debug(f"  + {article.title[:80]}...")
            except Exception as e:
                self.logger.warning(
                    f"Ошибка парсинга записи arXiv: {e}"
                )
                continue

        # Сохраняем в кэш
        self._save_to_cache(
            cache_key,
            [a.to_dict() for a in articles]
        )

        self.logger.info(
            f"arXiv: успешно получено {len(articles)} статей"
        )
        return articles