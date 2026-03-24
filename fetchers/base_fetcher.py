"""
Базовый класс для всех источников статей.

Определяет общий интерфейс, стандартную модель данных статьи,
механизм повторных попыток и кэширования.
"""

import time
import json
import hashlib
import logging
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from pathlib import Path

from config import Config


@dataclass
class Article:
    """
    Унифицированная модель научной статьи.
    
    Все источники возвращают данные в этом формате,
    что обеспечивает единообразие обработки.
    """
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    doi: Optional[str] = None
    url: str = ""
    pdf_url: Optional[str] = None
    year: Optional[int] = None
    journal: str = ""
    keywords: List[str] = field(default_factory=list)
    source: str = ""  # arxiv, elibrary, scopus, wos
    language: str = "en"  # Язык оригинала
    summary_ru: str = ""  # Резюме на русском
    abstract_ru: str = ""  # Аннотация на русском
    pdf_path: Optional[str] = None  # Путь к скачанному PDF
    raw_data: dict = field(default_factory=dict)  # Сырые данные источника

    def to_dict(self) -> dict:
        """Преобразование в словарь (без raw_data для экономии места)."""
        d = asdict(self)
        d.pop("raw_data", None)
        return d

    def __str__(self):
        return (
            f"[{self.source}] {self.title} "
            f"({self.year}) DOI: {self.doi or 'N/A'}"
        )


class BaseFetcher(ABC):
    """
    Абстрактный базовый класс для источников статей.
    
    Реализует:
    - HTTP-запросы с повторными попытками
    - Кэширование результатов
    - Логирование
    - Задержки между запросами (вежливость)
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"sci_agent.{name}")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "ScientificAgent/1.0 "
                "(Research Article Aggregator; Python/requests)"
            )
        })

    def _make_request(
        self,
        url: str,
        params: dict = None,
        headers: dict = None,
        method: str = "GET"
    ) -> Optional[requests.Response]:
        """
        HTTP-запрос с повторными попытками и обработкой ошибок.
        
        Args:
            url: URL запроса
            params: Параметры запроса
            headers: Дополнительные заголовки
            method: HTTP метод
            
        Returns:
            Response объект или None при неудаче
        """
        for attempt in range(1, Config.MAX_RETRIES + 1):
            try:
                self.logger.debug(
                    f"Запрос [{attempt}/{Config.MAX_RETRIES}]: "
                    f"{method} {url}"
                )

                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    timeout=Config.REQUEST_TIMEOUT
                )
                response.raise_for_status()

                # Вежливая задержка между запросами
                time.sleep(Config.POLITENESS_DELAY)

                return response

            except requests.exceptions.Timeout:
                self.logger.warning(
                    f"Таймаут запроса к {url} "
                    f"(попытка {attempt}/{Config.MAX_RETRIES})"
                )
            except requests.exceptions.ConnectionError as e:
                self.logger.warning(
                    f"Ошибка соединения с {url}: {e} "
                    f"(попытка {attempt}/{Config.MAX_RETRIES})"
                )
            except requests.exceptions.HTTPError as e:
                self.logger.warning(
                    f"HTTP ошибка {url}: {e} "
                    f"(попытка {attempt}/{Config.MAX_RETRIES})"
                )
                # Для 429 (Too Many Requests) увеличиваем задержку
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 429:
                        wait_time = Config.RETRY_DELAY * attempt * 2
                        self.logger.info(
                            f"Rate limit — ждём {wait_time}с"
                        )
                        time.sleep(wait_time)
                        continue
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Непредвиденная ошибка запроса: {e}")

            # Ожидание перед повторной попыткой
            if attempt < Config.MAX_RETRIES:
                wait_time = Config.RETRY_DELAY * attempt
                self.logger.info(f"Повтор через {wait_time}с...")
                time.sleep(wait_time)

        self.logger.error(
            f"Все {Config.MAX_RETRIES} попыток запроса к {url} исчерпаны"
        )
        return None

    def _get_cache_key(self, query: str, **kwargs) -> str:
        """Генерация ключа кэша на основе запроса."""
        cache_str = f"{self.name}:{query}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[List[dict]]:
        """Загрузка результатов из кэша."""
        cache_file = Config.CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            self.logger.info(f"Загрузка из кэша: {cache_file.name}")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Повреждённый кэш, удаляем")
                cache_file.unlink()
        return None

    def _save_to_cache(self, cache_key: str, data: List[dict]):
        """Сохранение результатов в кэш."""
        Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = Config.CACHE_DIR / f"{cache_key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.debug(f"Кэш сохранён: {cache_file.name}")

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> List[Article]:
        """
        Поиск статей по запросу.
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            
        Returns:
            Список объектов Article
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности источника."""
        pass