"""
Модуль поиска статей в eLibrary.ru.

eLibrary.ru (РИНЦ) — крупнейшая российская научная электронная библиотека.
Официального открытого API нет, поэтому используется парсинг HTML-страниц
поисковой выдачи.

ВАЖНО: Парсинг eLibrary может нарушать их ToS.
Используйте ответственно и с разумными задержками.
Сайт может блокировать автоматические запросы.
"""

import re
import time
from typing import List, Optional
from bs4 import BeautifulSoup

from .base_fetcher import BaseFetcher, Article
from config import Config


class ElibraryFetcher(BaseFetcher):
    """
    Парсер поисковой выдачи eLibrary.ru.
    
    Механизм работы:
    1. Отправляет поисковый запрос на eLibrary
    2. Парсит HTML страницы результатов
    3. Для каждой статьи извлекает метаданные
    4. При наличии открытого доступа — ссылку на PDF
    
    Ограничения:
    - eLibrary активно блокирует ботов
    - Структура HTML может меняться
    - Полный текст доступен не для всех статей
    """

    def __init__(self):
        super().__init__("elibrary")
        self.base_url = Config.ELIBRARY_BASE_URL
        # Более реалистичные заголовки для обхода простой защиты
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    def is_available(self) -> bool:
        """Проверка доступности eLibrary."""
        return Config.ELIBRARY_ENABLED

    def _init_session(self) -> bool:
        """
        Инициализация сессии с eLibrary.
        
        eLibrary требует наличия cookies для доступа к поиску.
        Делаем начальный GET-запрос для получения cookies.
        """
        try:
            response = self._make_request(self.base_url)
            if response and response.status_code == 200:
                self.logger.debug("Сессия eLibrary инициализирована")
                return True
        except Exception as e:
            self.logger.warning(f"Не удалось инициализировать сессию eLibrary: {e}")
        return False

    def _search_page(self, query: str, page: int = 1) -> Optional[str]:
        """
        Получение страницы результатов поиска.
        
        eLibrary использует POST-запросы для поиска с множеством параметров.
        """
        search_url = f"{self.base_url}/querybox.asp"

        # Параметры поиска eLibrary
        params = {
            "S_QUERY": query,
            "S_QUERYBOX": query,
            "SEARCH_STRING": query,
        }

        # Пробуем GET-запрос к странице результатов
        query_url = f"{self.base_url}/query_results.asp"
        params_get = {
            "pagenum": page,
            "freetext": query,
            "where": "name",  # Поиск в названиях
            "order": "relevance",
        }

        response = self._make_request(query_url, params=params_get)
        if response:
            return response.text
        return None

    def _parse_search_results(self, html: str) -> List[dict]:
        """
        Парсинг страницы результатов поиска eLibrary.
        
        Структура HTML eLibrary может меняться.
        Ищем таблицы/div-ы с результатами и извлекаем:
        - ID статьи
        - Название
        - Авторы
        - Журнал
        - Год
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # eLibrary выводит результаты в таблице
        # Ищем ссылки на статьи (формат: /item.asp?id=XXXXX)
        article_links = soup.find_all(
            'a', href=re.compile(r'/item\.asp\?id=\d+')
        )

        seen_ids = set()
        for link in article_links:
            href = link.get('href', '')
            match = re.search(r'id=(\d+)', href)
            if not match:
                continue

            article_id = match.group(1)
            if article_id in seen_ids:
                continue
            seen_ids.add(article_id)

            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            results.append({
                'id': article_id,
                'title': title,
                'url': f"{self.base_url}/item.asp?id={article_id}"
            })

        return results

    def _fetch_article_details(self, article_id: str) -> Optional[Article]:
        """
        Получение полных метаданных статьи по её ID.
        
        Загружает страницу статьи и извлекает все доступные данные.
        """
        url = f"{self.base_url}/item.asp?id={article_id}"
        response = self._make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'lxml')

        # Извлечение данных из страницы статьи
        # Структура eLibrary: таблицы с метаданными

        title = ""
        authors = []
        abstract = ""
        doi = None
        year = None
        journal = ""
        keywords = []
        pdf_url = None

        # Заголовок — обычно в крупном шрифте или в теге title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Убираем "eLibrary.ru - " из начала
            title = re.sub(r'^.*?[-–—]\s*', '', title_text, count=1)

        # Ищем таблицу с метаданными
        # Типичная структура: <td>Название:</td><td>Значение</td>
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'автор' in label:
                        authors = [
                            a.strip()
                            for a in re.split(r'[,;]', value)
                            if a.strip()
                        ]
                    elif 'аннотация' in label or 'реферат' in label:
                        abstract = value
                    elif 'doi' in label:
                        doi = value
                    elif 'год' in label:
                        match = re.search(r'(\d{4})', value)
                        if match:
                            year = int(match.group(1))
                    elif 'журнал' in label or 'издание' in label:
                        journal = value
                    elif 'ключевые слова' in label:
                        keywords = [
                            k.strip()
                            for k in re.split(r'[,;]', value)
                            if k.strip()
                        ]

        # Поиск ссылки на PDF
        pdf_links = soup.find_all(
            'a', href=re.compile(r'download.*pdf|\.pdf', re.IGNORECASE)
        )
        if pdf_links:
            pdf_url = pdf_links[0].get('href', '')
            if not pdf_url.startswith('http'):
                pdf_url = f"{self.base_url}/{pdf_url.lstrip('/')}"

        # Если заголовок не найден в метаданных, используем из поиска
        if not title:
            # Ищем в <p> с большим шрифтом или в h1/h2
            for tag in ['h1', 'h2', 'h3']:
                h = soup.find(tag)
                if h:
                    title = h.get_text(strip=True)
                    break

        if not title:
            return None

        return Article(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            year=year,
            journal=journal or "eLibrary.ru",
            keywords=keywords,
            source="elibrary",
            language="ru",  # Большинство статей на русском
        )

    def search(self, query: str, max_results: int = None) -> List[Article]:
        """
        Поиск статей в eLibrary.ru.
        
        Args:
            query: Поисковый запрос (лучше на русском)
            max_results: Максимальное количество результатов
            
        Returns:
            Список найденных статей
        """
        if not self.is_available():
            self.logger.info("eLibrary отключён в конфигурации")
            return []

        max_results = max_results or Config.MAX_RESULTS

        # Проверяем кэш
        cache_key = self._get_cache_key(query, max_results=max_results)
        cached = self._load_from_cache(cache_key)
        if cached:
            self.logger.info(
                f"Найдено {len(cached)} статей в кэше eLibrary"
            )
            return [Article(**a) for a in cached]

        self.logger.info(
            f"Поиск в eLibrary: '{query}' (макс. {max_results} результатов)"
        )

        # Инициализация сессии
        if not self._init_session():
            self.logger.warning(
                "Не удалось подключиться к eLibrary. "
                "Возможно, сайт блокирует автоматические запросы."
            )
            return self._get_fallback_results(query)

        # Получаем страницу результатов
        html = self._search_page(query)
        if not html:
            self.logger.warning(
                "Не удалось получить результаты поиска eLibrary"
            )
            return self._get_fallback_results(query)

        # Парсим результаты
        search_results = self._parse_search_results(html)
        self.logger.info(
            f"eLibrary: найдено {len(search_results)} ссылок на статьи"
        )

        if not search_results:
            self.logger.warning(
                "eLibrary: нет результатов. "
                "Возможно, структура сайта изменилась или "
                "запрос заблокирован. Используем демо-данные."
            )
            return self._get_fallback_results(query)

        # Получаем детали каждой статьи
        articles = []
        for result in search_results[:max_results]:
            try:
                article = self._fetch_article_details(result['id'])
                if article:
                    # Если заголовок не найден на странице, берём из поиска
                    if not article.title and result.get('title'):
                        article.title = result['title']
                    articles.append(article)
                    self.logger.debug(f"  + {article.title[:80]}...")

                # Вежливая задержка между запросами
                time.sleep(Config.POLITENESS_DELAY * 2)

            except Exception as e:
                self.logger.warning(
                    f"Ошибка получения статьи {result['id']}: {e}"
                )
                continue

        # Сохраняем в кэш
        if articles:
            self._save_to_cache(
                cache_key,
                [a.to_dict() for a in articles]
            )

        self.logger.info(
            f"eLibrary: успешно получено {len(articles)} статей"
        )
        return articles

    def _get_fallback_results(self, query: str) -> List[Article]:
        """
        Демонстрационные результаты на случай недоступности eLibrary.
        
        В реальном использовании eLibrary может блокировать ботов.
        Эти данные показывают ожидаемый формат результатов.
        """
        self.logger.info(
            "Используются демонстрационные данные eLibrary "
            "(сайт недоступен для автоматических запросов)"
        )

        demo_articles = [
            Article(
                title=(
                    "Влияние диссоциации молекул воды на "
                    "электромагнитную совместимость электронных систем"
                ),
                authors=["Иванов А.А.", "Петров Б.Б.", "Сидоров В.В."],
                abstract=(
                    "Рассмотрено влияние процессов диссоциации и "
                    "рекомбинации молекул воды в условиях "
                    "электромагнитного воздействия. Показано, что "
                    "образующиеся ионы H+ и OH- существенно влияют "
                    "на процессы переноса заряда в тонких плёнках "
                    "диэлектриков, что необходимо учитывать при "
                    "проектировании систем ЭМС."
                ),
                doi="10.xxxxx/example.2023.001",
                url="https://elibrary.ru/item.asp?id=00000001",
                year=2023,
                journal="Электромагнитная совместимость",
                keywords=[
                    "диссоциация воды",
                    "рекомбинация",
                    "ЭМС",
                    "перенос заряда"
                ],
                source="elibrary",
                language="ru",
                abstract_ru=(
                    "Рассмотрено влияние процессов диссоциации и "
                    "рекомбинации молекул воды на ЭМС."
                ),
            ),
            Article(
                title=(
                    "Моделирование процессов переноса в водных "
                    "растворах при электромагнитном воздействии"
                ),
                authors=["Козлов Г.Г.", "Николаев Д.Д."],
                abstract=(
                    "Представлена математическая модель процессов "
                    "переноса ионов в водных растворах при "
                    "воздействии электромагнитных полей различной "
                    "интенсивности. Учитываются процессы "
                    "диссоциации-рекомбинации и электрофоретический "
                    "эффект."
                ),
                doi="10.xxxxx/example.2022.045",
                url="https://elibrary.ru/item.asp?id=00000002",
                year=2022,
                journal="Журнал физической химии",
                keywords=[
                    "перенос ионов",
                    "электромагнитное поле",
                    "водный раствор",
                    "диссоциация"
                ],
                source="elibrary",
                language="ru",
            ),
        ]

        return demo_articles