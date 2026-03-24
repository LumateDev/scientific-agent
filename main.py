"""
Scientific Article Search Agent — Главный модуль.

Координирует работу всех компонентов:
1. Получает поисковый запрос
2. Запускает поиск по всем включённым источникам
3. Скачивает PDF (при наличии)
4. Генерирует резюме и переводы
5. Сохраняет результаты в БД
6. Формирует отчёты (JSON, HTML)

Использование:
    python main.py --query "dissociation recombination water" --max_results 20
    python main.py --web  # Запуск веб-интерфейса
    python main.py --clear-cache  # Очистка кэша

Автор: Scientific Agent
Лицензия: MIT
"""

import argparse
import logging
import sys
from typing import List
from tqdm import tqdm

from config import Config
from fetchers import ArxivFetcher, ElibraryFetcher, ScopusFetcher, WoSFetcher
from fetchers.base_fetcher import Article, BaseFetcher
from utils.translator import Translator
from utils.pdf_downloader import PDFDownloader
from utils.cache import CacheManager
from summarizer import Summarizer
from database import Database
from report_generator import ReportGenerator


class SearchAgent:
    """
    Главный агент поиска научных статей.
    
    Архитектура:
    ┌─────────────┐     ┌──────────────┐     ┌───────────────┐
    │   Fetchers  │────▶│   Agent      │────▶│   Reports     │
    │  (arXiv,    │     │  (обработка, │     │  (JSON, HTML, │
    │   eLibrary, │     │   перевод,   │     │   SQLite)     │
    │   Scopus,   │     │   резюме)    │     │               │
    │   WoS)      │     │              │     │               │
    └─────────────┘     └──────────────┘     └───────────────┘
    
    Каждый Fetcher работает независимо, результаты объединяются
    и обрабатываются централизованно.
    """

    def __init__(self):
        """Инициализация всех компонентов агента."""
        # Инициализация инфраструктуры
        Config.init_directories()
        self.logger = Config.setup_logging()
        self.logger.info("=" * 50)
        self.logger.info("Scientific Article Search Agent запущен")
        self.logger.info("=" * 50)

        # Инициализация компонентов
        self.translator = Translator()
        self.summarizer = Summarizer()
        self.downloader = PDFDownloader()
        self.reporter = ReportGenerator()
        self.cache_manager = CacheManager()

        # База данных
        self.db = None
        if Config.DB_ENABLED:
            self.db = Database()

        # Регистрация источников
        self.fetchers: List[BaseFetcher] = []
        self._register_fetchers()

    def _register_fetchers(self):
        """Регистрация и проверка доступных источников."""
        all_fetchers = [
            ArxivFetcher(),
            ElibraryFetcher(),
            ScopusFetcher(),
            WoSFetcher(),
        ]

        for fetcher in all_fetchers:
            if fetcher.is_available():
                self.fetchers.append(fetcher)
                self.logger.info(
                    f"✅ Источник зарегистрирован: {fetcher.name}"
                )
            else:
                self.logger.info(
                    f"⏭️  Источник пропущен (отключён): {fetcher.name}"
                )

        if not self.fetchers:
            self.logger.warning(
                "Нет доступных источников! "
                "Проверьте конфигурацию в .env"
            )

    def _process_article(self, article: Article) -> Article:
        """
        Обработка отдельной статьи:
        1. Перевод аннотации на русский (если на английском)
        2. Генерация резюме
        3. Скачивание PDF (если доступен)
        
        Args:
            article: Исходная статья
            
        Returns:
            Обработанная статья с переводом и резюме
        """
        # --- 1. Перевод аннотации ---
        if article.abstract and article.language == "en":
            try:
                article.abstract_ru = self.translator.translate(
                    article.abstract, source="en", target="ru"
                )
                self.logger.debug(
                    f"Переведена аннотация: {article.title[:50]}..."
                )
            except Exception as e:
                self.logger.warning(f"Ошибка перевода: {e}")
                article.abstract_ru = ""

        elif article.language == "ru":
            article.abstract_ru = article.abstract

        # --- 2. Генерация резюме ---
        # Для резюме используем доступный текст
        text_for_summary = article.abstract_ru or article.abstract
        if text_for_summary:
            try:
                article.summary_ru = self.summarizer.summarize(
                    text_for_summary,
                    language="russian" if article.abstract_ru else "english"
                )
                self.logger.debug(
                    f"Резюме сгенерировано: {article.title[:50]}..."
                )
            except Exception as e:
                self.logger.warning(f"Ошибка суммаризации: {e}")
                # Фоллбэк: первые 2 предложения
                sentences = text_for_summary.split('. ')
                article.summary_ru = '. '.join(sentences[:2]) + '.'

        # --- 3. Скачивание PDF ---
        if article.pdf_url:
            try:
                pdf_path = self.downloader.download(
                    url=article.pdf_url,
                    title=article.title,
                    article_id=article.doi or ""
                )
                if pdf_path:
                    article.pdf_path = pdf_path
            except Exception as e:
                self.logger.warning(
                    f"Ошибка скачивания PDF: {e}"
                )

        return article

    def search(
        self,
        query: str,
        max_results: int = None,
        download_pdf: bool = True,
        translate: bool = True
    ) -> List[Article]:
        """
        Главный метод поиска.
        
        Выполняет поиск по всем зарегистрированным источникам,
        обрабатывает результаты и возвращает единый список статей.
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов на источник
            download_pdf: Скачивать ли PDF-файлы
            translate: Переводить ли аннотации
            
        Returns:
            Список обработанных статей
        """
        max_results = max_results or Config.MAX_RESULTS

        self.logger.info(f"🔍 Запрос: '{query}'")
        self.logger.info(
            f"📊 Макс. результатов на источник: {max_results}"
        )
        self.logger.info(
            f"📥 Скачивание PDF: {'Да' if download_pdf else 'Нет'}"
        )

        all_articles: List[Article] = []

        # --- Фаза 1: Сбор статей из всех источников ---
        print("\n📚 Фаза 1: Поиск статей по источникам\n")

        for fetcher in tqdm(
            self.fetchers, desc="Источники", unit="src"
        ):
            self.logger.info(
                f"🔎 Поиск в {fetcher.name.upper()}..."
            )
            try:
                # Для eLibrary используем русский запрос
                search_query = query
                if fetcher.name == "elibrary":
                    search_query = Config.DEFAULT_QUERY_RU

                articles = fetcher.search(
                    search_query, max_results=max_results
                )
                all_articles.extend(articles)
                self.logger.info(
                    f"  → {fetcher.name}: {len(articles)} статей"
                )

            except Exception as e:
                self.logger.error(
                    f"Критическая ошибка {fetcher.name}: {e}"
                )
                continue

        if not all_articles:
            self.logger.warning("Статьи не найдены ни в одном источнике")
            return []

        self.logger.info(f"\n📊 Всего собрано: {len(all_articles)} статей")

        # --- Фаза 2: Обработка статей ---
        print(f"\n🔧 Фаза 2: Обработка {len(all_articles)} статей\n")

        processed_articles = []
        for article in tqdm(
            all_articles, desc="Обработка", unit="art"
        ):
            try:
                if not download_pdf:
                    article.pdf_url = None  # Пропускаем скачивание

                if translate:
                    processed = self._process_article(article)
                else:
                    processed = article
                    # Даже без перевода генерируем резюме
                    if article.abstract:
                        article.summary_ru = self.summarizer.summarize(
                            article.abstract
                        )

                processed_articles.append(processed)

            except Exception as e:
                self.logger.warning(
                    f"Ошибка обработки '{article.title[:50]}': {e}"
                )
                processed_articles.append(article)

        # --- Фаза 3: Дедупликация ---
        unique_articles = self._deduplicate(processed_articles)
        self.logger.info(
            f"После дедупликации: {len(unique_articles)} статей"
        )

        # --- Фаза 4: Сохранение в БД ---
        if self.db:
            sources = [f.name for f in self.fetchers]
            self.db.save_search(query, sources, unique_articles)
            self.logger.info("Результаты сохранены в БД")

        return unique_articles

    def _deduplicate(self, articles: List[Article]) -> List[Article]:
        """
        Дедупликация статей по DOI и заголовку.
        
        Одна и та же статья может быть найдена в нескольких
        источниках. Отдаём приоритет записям с большим
        количеством данных (DOI, PDF и т.д.).
        """
        seen_dois = set()
        seen_titles = set()
        unique = []

        for article in articles:
            # Проверяем DOI
            if article.doi:
                doi_lower = article.doi.lower().strip()
                if doi_lower in seen_dois:
                    continue
                seen_dois.add(doi_lower)

            # Проверяем заголовок (нормализованный)
            title_norm = article.title.lower().strip()
            # Убираем знаки препинания для сравнения
            title_norm = ''.join(
                c for c in title_norm if c.isalnum() or c.isspace()
            )
            title_norm = ' '.join(title_norm.split())

            if title_norm in seen_titles:
                continue
            seen_titles.add(title_norm)

            unique.append(article)

        removed = len(articles) - len(unique)
        if removed:
            self.logger.info(f"Удалено дубликатов: {removed}")

        return unique


def main():
    """Точка входа приложения."""
    parser = argparse.ArgumentParser(
        description="🔬 Scientific Article Search Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py --query "dissociation recombination water transport"
  python main.py --query "water molecules electromagnetic" --max_results 20
  python main.py --web                  # Запуск веб-интерфейса
  python main.py --clear-cache          # Очистка кэша
  python main.py --no-pdf --no-translate  # Быстрый поиск без PDF и перевода
        """
    )

    parser.add_argument(
        '--query', '-q',
        type=str,
        default=Config.DEFAULT_QUERY,
        help='Поисковый запрос (по умолчанию из конфига)'
    )
    parser.add_argument(
        '--max_results', '-n',
        type=int,
        default=Config.MAX_RESULTS,
        help=f'Максимум результатов на источник (по умолчанию: {Config.MAX_RESULTS})'
    )
    parser.add_argument(
        '--no-pdf',
        action='store_true',
        help='Не скачивать PDF-файлы'
    )
    parser.add_argument(
        '--no-translate',
        action='store_true',
        help='Не переводить аннотации'
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Генерировать только JSON (без HTML)'
    )
    parser.add_argument(
        '--web',
        action='store_true',
        help='Запустить веб-интерфейс (Flask)'
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Очистить кэш и выйти'
    )
    parser.add_argument(
        '--db-stats',
        action='store_true',
        help='Показать статистику БД и выйти'
    )

    args = parser.parse_args()

    # --- Режим очистки кэша ---
    if args.clear_cache:
        Config.init_directories()
        cache = CacheManager()
        print(f"Статистика кэша: {cache.stats()}")
        cache.clear()
        print("✅ Кэш очищен")
        return

    # --- Режим веб-интерфейса ---
    if args.web:
        from web_app import run_web
        run_web()
        return

    # --- Режим статистики БД ---
    if args.db_stats:
        Config.init_directories()
        if Config.DB_ENABLED:
            db = Database()
            stats = db.get_stats()
            print("\n📊 Статистика базы данных:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        else:
            print("БД отключена в конфигурации")
        return

    # --- Основной режим: поиск ---
    print("\n🔬 Scientific Article Search Agent")
    print("=" * 50)
    print(f"Запрос: {args.query}")
    print(f"Макс. результатов: {args.max_results}")
    print(f"PDF: {'Нет' if args.no_pdf else 'Да'}")
    print(f"Перевод: {'Нет' if args.no_translate else 'Да'}")
    print("=" * 50)

    # Создаём агента и запускаем поиск
    agent = SearchAgent()

    articles = agent.search(
        query=args.query,
        max_results=args.max_results,
        download_pdf=not args.no_pdf,
        translate=not args.no_translate
    )

    if not articles:
        print("\n⚠️ Статьи не найдены. Попробуйте другой запрос.")
        return

    # --- Генерация отчётов ---
    print(f"\n📝 Генерация отчётов...")

    reporter = ReportGenerator()

    # JSON (всегда)
    json_path = reporter.generate_json(articles, args.query)
    print(f"  ✅ JSON: {json_path}")

    # HTML (по умолчанию)
    if not args.json_only:
        html_path = reporter.generate_html(articles, args.query)
        print(f"  ✅ HTML: {html_path}")

    # Вывод сводки в консоль
    reporter.print_summary(articles, args.query)

    # Статистика кэша
    cache_stats = agent.cache_manager.stats()
    print(f"\n📦 Кэш: {cache_stats['files']} файлов, "
          f"{cache_stats['total_size_kb']} КБ")

    # Статистика БД
    if agent.db:
        db_stats = agent.db.get_stats()
        print(f"🗄️  БД: {db_stats['total_articles']} статей всего")

    print("\n✅ Готово!")


if __name__ == "__main__":
    main()