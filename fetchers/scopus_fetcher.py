"""
Модуль поиска статей в Scopus (Elsevier).

Scopus — крупнейшая реферативная база данных научных публикаций.
Требует API-ключ для доступа (бесплатный для некоммерческого использования).

Получение ключа: https://dev.elsevier.com/
Документация API: https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl
"""

import re
from typing import List, Optional

from .base_fetcher import BaseFetcher, Article
from config import Config


class ScopusFetcher(BaseFetcher):
    """
    Поиск статей через Scopus API (Elsevier).
    
    Работает в двух режимах:
    1. С API-ключом: реальные запросы к Scopus
    2. Без ключа: демонстрационные данные (заглушка)
    """

    def __init__(self):
        super().__init__("scopus")
        self.base_url = Config.SCOPUS_BASE_URL
        self.api_key = Config.SCOPUS_API_KEY

    def is_available(self) -> bool:
        """
        Scopus доступен только при наличии API-ключа.
        Если ключ не задан — используется заглушка.
        """
        return Config.SCOPUS_ENABLED

    def _has_api_key(self) -> bool:
        """Проверка наличия действующего ключа."""
        return bool(
            self.api_key
            and self.api_key != "your_scopus_api_key_here"
        )

    def _build_query(self, query: str) -> str:
        """
        Построение запроса в формате Scopus Search API.
        
        Scopus использует синтаксис:
        TITLE-ABS-KEY(term1 AND term2)
        """
        terms = query.strip().split()
        terms_clean = [
            t for t in terms
            if t.upper() not in ("AND", "OR", "NOT")
        ]
        scopus_query = "TITLE-ABS-KEY(" + " AND ".join(terms_clean) + ")"
        self.logger.debug(f"Scopus запрос: {scopus_query}")
        return scopus_query

    def _parse_scopus_entry(self, entry: dict) -> Article:
        """Преобразование записи Scopus в Article."""
        # Авторы
        authors_str = entry.get("dc:creator", "")
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]

        # DOI
        doi = entry.get("prism:doi")

        # Год
        year = None
        cover_date = entry.get("prism:coverDate", "")
        if cover_date:
            match = re.search(r"(\d{4})", cover_date)
            if match:
                year = int(match.group(1))

        # Ссылки
        url = ""
        for link in entry.get("link", []):
            if link.get("@ref") == "scopus":
                url = link.get("@href", "")
                break

        return Article(
            title=entry.get("dc:title", ""),
            authors=authors,
            abstract=entry.get("dc:description", ""),
            doi=doi,
            url=url,
            year=year,
            journal=entry.get("prism:publicationName", ""),
            keywords=[],
            source="scopus",
            language="en",
            raw_data=entry,
        )

    def search(self, query: str, max_results: int = None) -> List[Article]:
        """
        Поиск статей в Scopus.
        
        При отсутствии API-ключа возвращает демо-данные.
        """
        if not self.is_available():
            self.logger.info("Scopus отключён в конфигурации")
            return []

        max_results = max_results or Config.MAX_RESULTS

        # Проверяем кэш
        cache_key = self._get_cache_key(query, max_results=max_results)
        cached = self._load_from_cache(cache_key)
        if cached:
            return [Article(**a) for a in cached]

        # Если нет ключа — возвращаем заглушку
        if not self._has_api_key():
            self.logger.warning(
                "Scopus API-ключ не задан. "
                "Используются демонстрационные данные.\n"
                "Для получения ключа: https://dev.elsevier.com/"
            )
            return self._get_demo_results(query)

        # Реальный запрос к Scopus API
        self.logger.info(f"Поиск в Scopus: '{query}'")

        scopus_query = self._build_query(query)
        params = {
            "query": scopus_query,
            "count": max_results,
            "start": 0,
            "sort": "relevancy",
            "view": "STANDARD",
        }
        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        }

        response = self._make_request(
            self.base_url, params=params, headers=headers
        )

        if not response:
            self.logger.error("Не удалось получить ответ от Scopus")
            return self._get_demo_results(query)

        try:
            data = response.json()
            results = data.get("search-results", {})
            entries = results.get("entry", [])

            total = results.get("opensearch:totalResults", "0")
            self.logger.info(f"Scopus: найдено {total} результатов")

            articles = []
            for entry in entries:
                try:
                    article = self._parse_scopus_entry(entry)
                    articles.append(article)
                except Exception as e:
                    self.logger.warning(
                        f"Ошибка парсинга записи Scopus: {e}"
                    )

            # Кэширование
            self._save_to_cache(
                cache_key, [a.to_dict() for a in articles]
            )

            return articles

        except Exception as e:
            self.logger.error(f"Ошибка обработки ответа Scopus: {e}")
            return self._get_demo_results(query)

    def _get_demo_results(self, query: str) -> List[Article]:
        """
        Демонстрационные результаты Scopus.
        
        Показывают формат данных, который возвращает реальный API.
        """
        self.logger.info("Scopus: используются демонстрационные данные")

        return [
            Article(
                title=(
                    "Water dissociation and recombination effects on "
                    "charge transport in electromagnetic environments"
                ),
                authors=["Smith, J.A.", "Johnson, R.B.", "Williams, K.C."],
                abstract=(
                    "This study investigates the influence of water "
                    "molecule dissociation and recombination processes "
                    "on charge carrier transport mechanisms in systems "
                    "exposed to electromagnetic fields. The results "
                    "demonstrate significant impact on electromagnetic "
                    "compatibility parameters of electronic systems."
                ),
                doi="10.1016/j.example.2023.100001",
                url="https://www.scopus.com/record/display.uri?eid=DEMO",
                year=2023,
                journal="Journal of Electromagnetic Compatibility",
                keywords=[
                    "water dissociation",
                    "charge transport",
                    "EMC",
                    "recombination"
                ],
                source="scopus",
                language="en",
            ),
            Article(
                title=(
                    "Molecular dynamics simulation of H2O "
                    "dissociation-recombination kinetics under "
                    "electromagnetic stress"
                ),
                authors=["Chen, L.", "Wang, M.", "Park, S."],
                abstract=(
                    "Molecular dynamics simulations were performed to "
                    "study the kinetics of water dissociation and "
                    "recombination under varying electromagnetic field "
                    "strengths. Transport properties including "
                    "diffusion coefficients and ionic conductivity "
                    "were calculated."
                ),
                doi="10.1021/acs.example.2022.54321",
                url="https://www.scopus.com/record/display.uri?eid=DEMO2",
                year=2022,
                journal="ACS Physical Chemistry",
                keywords=[
                    "molecular dynamics",
                    "water",
                    "electromagnetic field",
                    "transport properties"
                ],
                source="scopus",
                language="en",
            ),
        ]