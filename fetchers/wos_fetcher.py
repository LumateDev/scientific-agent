"""
Модуль поиска статей в Web of Science (Clarivate Analytics).

Web of Science Starter API предоставляет ограниченный бесплатный доступ.
Полный API (Web of Science Expanded API) требует подписки.

Документация: https://developer.clarivate.com/apis/wos-starter
Получение ключа: https://developer.clarivate.com/
"""

import re
from typing import List, Optional

from .base_fetcher import BaseFetcher, Article
from config import Config


class WoSFetcher(BaseFetcher):
    """
    Поиск статей через Web of Science API.
    
    Режимы работы:
    1. С API-ключом: запросы к WoS Starter API
    2. Без ключа: демонстрационные данные (заглушка)
    """

    def __init__(self):
        super().__init__("wos")
        self.base_url = Config.WOS_BASE_URL
        self.api_key = Config.WOS_API_KEY

    def is_available(self) -> bool:
        return Config.WOS_ENABLED

    def _has_api_key(self) -> bool:
        return bool(
            self.api_key
            and self.api_key != "your_wos_api_key_here"
        )

    def _build_query(self, query: str) -> str:
        """
        Построение запроса WoS.
        
        WoS Starter API использует упрощённый запрос (q parameter).
        """
        return query

    def _parse_wos_entry(self, entry: dict) -> Article:
        """Преобразование записи WoS в Article."""
        # Извлечение данных из структуры WoS API
        names = entry.get("names", {})
        authors_list = names.get("authors", [])
        authors = [
            a.get("displayName", a.get("wosStandard", ""))
            for a in authors_list
        ]

        # Идентификаторы
        identifiers = entry.get("identifiers", {})
        doi = identifiers.get("doi")

        # Источник
        source_info = entry.get("source", {})
        journal = source_info.get("sourceTitle", "")
        year_str = source_info.get("publishYear", "")
        year = int(year_str) if year_str else None

        # Ссылки
        links = entry.get("links", {})
        url = links.get("record", "")

        return Article(
            title=entry.get("title", ""),
            authors=authors,
            abstract="",  # WoS Starter API может не давать абстракт
            doi=doi,
            url=url,
            year=year,
            journal=journal,
            keywords=entry.get("keywords", {}).get("authorKeywords", []),
            source="wos",
            language="en",
            raw_data=entry,
        )

    def search(self, query: str, max_results: int = None) -> List[Article]:
        """Поиск статей в Web of Science."""
        if not self.is_available():
            self.logger.info("Web of Science отключён в конфигурации")
            return []

        max_results = max_results or Config.MAX_RESULTS

        # Кэш
        cache_key = self._get_cache_key(query, max_results=max_results)
        cached = self._load_from_cache(cache_key)
        if cached:
            return [Article(**a) for a in cached]

        if not self._has_api_key():
            self.logger.warning(
                "Web of Science API-ключ не задан. "
                "Используются демонстрационные данные.\n"
                "Получение ключа: https://developer.clarivate.com/"
            )
            return self._get_demo_results(query)

        # Реальный запрос
        self.logger.info(f"Поиск в WoS: '{query}'")

        search_url = f"{self.base_url}/documents"
        params = {
            "q": self._build_query(query),
            "limit": min(max_results, 50),  # WoS лимит
            "page": 1,
            "sortField": "relevance",
            "order": "desc",
        }
        headers = {
            "X-ApiKey": self.api_key,
            "Accept": "application/json",
        }

        response = self._make_request(
            search_url, params=params, headers=headers
        )

        if not response:
            return self._get_demo_results(query)

        try:
            data = response.json()
            hits = data.get("hits", [])

            self.logger.info(
                f"WoS: найдено {data.get('metadata', {}).get('total', 0)} результатов"
            )

            articles = []
            for hit in hits:
                try:
                    article = self._parse_wos_entry(hit)
                    articles.append(article)
                except Exception as e:
                    self.logger.warning(f"Ошибка парсинга WoS: {e}")

            self._save_to_cache(
                cache_key, [a.to_dict() for a in articles]
            )
            return articles

        except Exception as e:
            self.logger.error(f"Ошибка обработки ответа WoS: {e}")
            return self._get_demo_results(query)

    def _get_demo_results(self, query: str) -> List[Article]:
        """Демонстрационные результаты Web of Science."""
        self.logger.info("WoS: демонстрационные данные")

        return [
            Article(
                title=(
                    "Transport phenomena in aqueous systems: "
                    "Role of water autoionization under "
                    "electromagnetic perturbation"
                ),
                authors=["Anderson, P.", "Mueller, H.", "Tanaka, Y."],
                abstract=(
                    "We present a comprehensive study of transport "
                    "phenomena in aqueous electrolyte systems under "
                    "electromagnetic perturbation. The role of water "
                    "autoionization (H2O ⇌ H+ + OH-) is analyzed "
                    "in the context of charge transport and "
                    "electromagnetic compatibility of electronic "
                    "equipment operating in humid environments."
                ),
                doi="10.1088/example.2023.001",
                url="https://www.webofscience.com/wos/DEMO",
                year=2023,
                journal="Journal of Physics D: Applied Physics",
                keywords=[
                    "autoionization",
                    "transport phenomena",
                    "electromagnetic compatibility",
                    "aqueous systems"
                ],
                source="wos",
                language="en",
            ),
        ]