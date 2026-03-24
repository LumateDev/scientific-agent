"""
Модуль генерации отчётов.

Форматы:
- JSON: структурированные данные для программной обработки
- HTML: визуальный отчёт с карточками статей
- Текстовый: для быстрого просмотра в консоли
"""

import json
import logging
from typing import List
from datetime import datetime
from pathlib import Path

from config import Config
from fetchers.base_fetcher import Article

logger = logging.getLogger("sci_agent.report")

# HTML-шаблон встроен для автономности (без зависимости от Jinja2 файлов)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Научный отчёт: {{ query }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            color: #333;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        header {
            background: linear-gradient(135deg, #1a5276, #2980b9);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        header h1 { font-size: 1.8em; margin-bottom: 10px; }
        header .meta { opacity: 0.9; font-size: 0.95em; }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .stat-card .number {
            font-size: 2em;
            font-weight: bold;
            color: #2980b9;
        }
        .stat-card .label { color: #666; margin-top: 5px; }
        
        .article-card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            border-left: 4px solid #2980b9;
        }
        .article-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        }
        .article-card .source-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .source-arxiv { background: #e8f5e9; color: #2e7d32; }
        .source-elibrary { background: #fff3e0; color: #e65100; }
        .source-scopus { background: #e3f2fd; color: #1565c0; }
        .source-wos { background: #f3e5f5; color: #7b1fa2; }
        
        .article-card h2 {
            font-size: 1.2em;
            margin-bottom: 8px;
            color: #1a5276;
        }
        .article-card h2 a {
            color: inherit;
            text-decoration: none;
        }
        .article-card h2 a:hover { text-decoration: underline; }
        
        .article-card .authors {
            color: #666;
            margin-bottom: 8px;
            font-style: italic;
        }
        .article-card .meta-info {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 12px;
            font-size: 0.9em;
            color: #555;
        }
        .article-card .meta-info span {
            background: #f5f5f5;
            padding: 2px 8px;
            border-radius: 4px;
        }
        .article-card .abstract {
            margin-bottom: 12px;
            color: #444;
        }
        .article-card .summary {
            background: #f8f9fa;
            border-left: 3px solid #28a745;
            padding: 12px 15px;
            margin-bottom: 12px;
            border-radius: 0 6px 6px 0;
        }
        .article-card .summary h4 {
            color: #28a745;
            margin-bottom: 5px;
        }
        .article-card .keywords {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .article-card .keywords span {
            background: #e8eaf6;
            color: #3f51b5;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
        }
        
        footer {
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 0.85em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔬 Научный отчёт по поиску статей</h1>
            <div class="meta">
                <p><strong>Запрос:</strong> {{ query }}</p>
                <p><strong>Дата:</strong> {{ date }}</p>
                <p><strong>Источники:</strong> {{ sources }}</p>
            </div>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="number">{{ total }}</div>
                <div class="label">Всего статей</div>
            </div>
            {{ stats_cards }}
        </div>
        
        {{ article_cards }}
        
        <footer>
            <p>Сгенерировано Scientific Article Search Agent</p>
            <p>{{ date }}</p>
        </footer>
    </div>
</body>
</html>"""


class ReportGenerator:
    """
    Генератор отчётов в различных форматах.
    
    Поддерживает JSON, HTML и текстовый вывод.
    HTML-отчёт создаётся без внешних зависимостей (шаблон встроен).
    """

    def __init__(self):
        Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def generate_json(
        self,
        articles: List[Article],
        query: str,
        filename: str = None
    ) -> str:
        """
        Генерация JSON-отчёта.
        
        Returns:
            Путь к файлу
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.json"

        filepath = Config.OUTPUT_DIR / filename

        report_data = {
            "meta": {
                "query": query,
                "date": datetime.now().isoformat(),
                "total_results": len(articles),
                "sources": list(set(a.source for a in articles)),
            },
            "articles": [a.to_dict() for a in articles]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON-отчёт сохранён: {filepath}")
        return str(filepath)

    def generate_html(
        self,
        articles: List[Article],
        query: str,
        filename: str = None
    ) -> str:
        """
        Генерация HTML-отчёта с карточками статей.
        
        Returns:
            Путь к файлу
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.html"

        filepath = Config.OUTPUT_DIR / filename

        # Подсчёт статистики по источникам
        source_counts = {}
        for a in articles:
            source_counts[a.source] = source_counts.get(a.source, 0) + 1

        # Карточки статистики
        stats_cards = ""
        for source, count in source_counts.items():
            stats_cards += f"""
            <div class="stat-card">
                <div class="number">{count}</div>
                <div class="label">{source.upper()}</div>
            </div>"""

        # Карточки статей
        article_cards = ""
        for i, article in enumerate(articles, 1):
            source_class = f"source-{article.source}"

            # Авторы
            authors_str = ", ".join(article.authors[:5])
            if len(article.authors) > 5:
                authors_str += f" и ещё {len(article.authors) - 5}"

            # Мета-информация
            meta_parts = []
            if article.year:
                meta_parts.append(f"<span>📅 {article.year}</span>")
            if article.journal:
                meta_parts.append(
                    f"<span>📰 {article.journal[:60]}</span>"
                )
            if article.doi:
                meta_parts.append(
                    f'<span>🔗 <a href="https://doi.org/{article.doi}" '
                    f'target="_blank">{article.doi}</a></span>'
                )
            if article.pdf_url:
                meta_parts.append(
                    f'<span>📄 <a href="{article.pdf_url}" '
                    f'target="_blank">PDF</a></span>'
                )
            meta_html = "\n".join(meta_parts)

            # Резюме
            summary_html = ""
            if article.summary_ru:
                summary_html = f"""
                <div class="summary">
                    <h4>📝 Резюме (RU)</h4>
                    <p>{article.summary_ru}</p>
                </div>"""

            # Аннотация на русском
            abstract_ru_html = ""
            if article.abstract_ru and article.abstract_ru != article.abstract:
                abstract_ru_html = f"""
                <div class="summary" style="border-left-color: #2196F3;">
                    <h4>🌐 Аннотация (перевод)</h4>
                    <p>{article.abstract_ru}</p>
                </div>"""

            # Ключевые слова
            keywords_html = ""
            if article.keywords:
                kw_spans = "".join(
                    f"<span>{kw}</span>" for kw in article.keywords[:10]
                )
                keywords_html = f"""
                <div class="keywords">{kw_spans}</div>"""

            # Абстракт (оригинал) — обрезаем до 500 символов
            abstract_display = article.abstract[:500]
            if len(article.abstract) > 500:
                abstract_display += "..."

            article_cards += f"""
            <div class="article-card">
                <span class="source-badge {source_class}">
                    {article.source}
                </span>
                <h2>
                    <a href="{article.url}" target="_blank">
                        {i}. {article.title}
                    </a>
                </h2>
                <div class="authors">👤 {authors_str or 'Авторы не указаны'}</div>
                <div class="meta-info">{meta_html}</div>
                <div class="abstract">
                    <strong>Abstract:</strong> {abstract_display}
                </div>
                {abstract_ru_html}
                {summary_html}
                {keywords_html}
            </div>"""

        # Сборка HTML
        html = HTML_TEMPLATE
        html = html.replace("{{ query }}", query)
        html = html.replace(
            "{{ date }}",
            datetime.now().strftime("%d.%m.%Y %H:%M")
        )
        html = html.replace(
            "{{ sources }}",
            ", ".join(source_counts.keys())
        )
        html = html.replace("{{ total }}", str(len(articles)))
        html = html.replace("{{ stats_cards }}", stats_cards)
        html = html.replace("{{ article_cards }}", article_cards)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"HTML-отчёт сохранён: {filepath}")
        return str(filepath)

    def print_summary(self, articles: List[Article], query: str):
        """Вывод краткой сводки в консоль."""
        print("\n" + "=" * 70)
        print(f"🔬 РЕЗУЛЬТАТЫ ПОИСКА: {query}")
        print(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        print(f"📊 Найдено статей: {len(articles)}")
        print("=" * 70)

        # Статистика по источникам
        source_counts = {}
        for a in articles:
            source_counts[a.source] = source_counts.get(a.source, 0) + 1

        print("\nИсточники:")
        for source, count in source_counts.items():
            print(f"  • {source.upper()}: {count} статей")

        print("\n" + "-" * 70)

        for i, article in enumerate(articles, 1):
            print(f"\n📄 [{i}] [{article.source.upper()}] {article.title}")
            if article.authors:
                print(f"   👤 {', '.join(article.authors[:3])}")
            if article.year:
                print(f"   📅 {article.year}")
            if article.doi:
                print(f"   🔗 DOI: {article.doi}")
            if article.summary_ru:
                # Обрезаем длинное резюме
                summary = article.summary_ru[:200]
                if len(article.summary_ru) > 200:
                    summary += "..."
                print(f"   📝 {summary}")
            print()

        print("=" * 70)