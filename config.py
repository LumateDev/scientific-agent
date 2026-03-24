"""
Конфигурация проекта.

Загружает настройки из .env файла и предоставляет
централизованный доступ ко всем параметрам.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


class Config:
    """Централизованная конфигурация приложения."""

    # --- Базовые пути ---
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
    CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
    LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
    PDF_DIR = Path(os.getenv("PDF_DIR", "./output/pdfs"))

    # --- Общие настройки ---
    MAX_RESULTS = int(os.getenv("MAX_RESULTS", "20"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = float(os.getenv("RETRY_DELAY", "2"))
    POLITENESS_DELAY = float(os.getenv("POLITENESS_DELAY", "1.0"))

    # --- Источники ---
    ARXIV_ENABLED = os.getenv("ARXIV_ENABLED", "true").lower() == "true"
    ARXIV_BASE_URL = os.getenv(
        "ARXIV_BASE_URL", "http://export.arxiv.org/api/query"
    )

    ELIBRARY_ENABLED = os.getenv("ELIBRARY_ENABLED", "true").lower() == "true"
    ELIBRARY_BASE_URL = os.getenv(
        "ELIBRARY_BASE_URL", "https://www.elibrary.ru"
    )

    SCOPUS_ENABLED = os.getenv("SCOPUS_ENABLED", "false").lower() == "true"
    SCOPUS_API_KEY = os.getenv("SCOPUS_API_KEY", "")
    SCOPUS_BASE_URL = os.getenv(
        "SCOPUS_BASE_URL",
        "https://api.elsevier.com/content/search/scopus"
    )

    WOS_ENABLED = os.getenv("WOS_ENABLED", "false").lower() == "true"
    WOS_API_KEY = os.getenv("WOS_API_KEY", "")
    WOS_BASE_URL = os.getenv(
        "WOS_BASE_URL",
        "https://api.clarivate.com/apis/wos-starter/v1"
    )

    # --- Перевод и суммаризация ---
    TRANSLATOR = os.getenv("TRANSLATOR", "google")
    YANDEX_TRANSLATE_API_KEY = os.getenv("YANDEX_TRANSLATE_API_KEY", "")
    SUMMARIZER = os.getenv("SUMMARIZER", "extractive")
    SUMMARY_SENTENCES = int(os.getenv("SUMMARY_SENTENCES", "5"))

    # --- БД ---
    DB_ENABLED = os.getenv("DB_ENABLED", "true").lower() == "true"
    DB_PATH = Path(os.getenv("DB_PATH", "./output/articles.db"))

    # --- Telegram ---
    TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Flask ---
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # --- Тема по умолчанию ---
    DEFAULT_QUERY = os.getenv(
        "DEFAULT_QUERY",
        "dissociation recombination water molecules transport electromagnetic"
    )
    DEFAULT_QUERY_RU = os.getenv(
        "DEFAULT_QUERY_RU",
        "диссоциация рекомбинация молекул воды процессы переноса ЭМС"
    )

    @classmethod
    def init_directories(cls):
        """Создание необходимых директорий."""
        for dir_path in [cls.OUTPUT_DIR, cls.CACHE_DIR, cls.LOG_DIR, cls.PDF_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def setup_logging(cls) -> logging.Logger:
        """Настройка логирования с выводом в файл и консоль."""
        cls.init_directories()
        log_file = cls.LOG_DIR / "agent.log"

        # Форматирование
        formatter = logging.Formatter(
            "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Файловый обработчик
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # Корневой логгер
        logger = logging.getLogger("sci_agent")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger