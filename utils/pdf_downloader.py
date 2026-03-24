"""
Модуль скачивания PDF-файлов.

Скачивает полные тексты статей из открытого доступа:
- arXiv: PDF всегда доступен
- eLibrary: PDF доступен для части статей (открытый доступ)
- Другие источники: по наличию ссылки на PDF
"""

import re
import logging
import requests
from pathlib import Path
from typing import Optional
from tqdm import tqdm

from config import Config

logger = logging.getLogger("sci_agent.pdf_downloader")


class PDFDownloader:
    """
    Менеджер скачивания PDF-файлов.
    
    Функционал:
    - Скачивание с прогресс-баром
    - Проверка, не скачан ли файл ранее
    - Генерация удобных имён файлов
    - Обработка ошибок и повторные попытки
    """

    def __init__(self):
        Config.PDF_DIR.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "ScientificAgent/1.0 (PDF Downloader; Python/requests)"
            )
        })

    def _sanitize_filename(self, title: str, max_length: int = 80) -> str:
        """
        Создание безопасного имени файла из заголовка статьи.
        
        Убирает специальные символы, обрезает до max_length.
        """
        # Убираем всё кроме букв, цифр, пробелов, дефисов
        safe = re.sub(r'[^\w\s\-]', '', title, flags=re.UNICODE)
        # Заменяем пробелы на подчёркивания
        safe = re.sub(r'\s+', '_', safe.strip())
        # Обрезаем
        if len(safe) > max_length:
            safe = safe[:max_length]
        return safe or "untitled"

    def download(
        self,
        url: str,
        title: str = "",
        article_id: str = ""
    ) -> Optional[str]:
        """
        Скачивание PDF-файла.
        
        Args:
            url: URL файла
            title: Заголовок статьи (для имени файла)
            article_id: ID статьи (для имени файла)
            
        Returns:
            Путь к скачанному файлу или None
        """
        if not url:
            logger.debug("Пустой URL для скачивания PDF")
            return None

        # Генерируем имя файла
        if title:
            filename = f"{self._sanitize_filename(title)}.pdf"
        elif article_id:
            filename = f"{article_id}.pdf"
        else:
            filename = re.sub(r'[^\w.]', '_', url.split('/')[-1])
            if not filename.endswith('.pdf'):
                filename += '.pdf'

        filepath = Config.PDF_DIR / filename

        # Проверяем, не скачан ли уже
        if filepath.exists() and filepath.stat().st_size > 0:
            logger.debug(f"PDF уже скачан: {filepath.name}")
            return str(filepath)

        logger.info(f"Скачивание PDF: {url}")
        logger.debug(f"  → {filepath}")

        try:
            response = self.session.get(
                url,
                stream=True,
                timeout=Config.REQUEST_TIMEOUT * 2,
                allow_redirects=True
            )
            response.raise_for_status()

            # Проверяем, что это действительно PDF
            content_type = response.headers.get('Content-Type', '')
            if 'html' in content_type and 'pdf' not in content_type:
                logger.warning(
                    f"Ответ не является PDF ({content_type}): {url}"
                )
                return None

            # Размер файла
            total_size = int(response.headers.get('Content-Length', 0))

            # Скачиваем с прогресс-баром
            with open(filepath, 'wb') as f:
                if total_size > 0:
                    with tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        desc=f"PDF {filepath.name[:40]}",
                        leave=False
                    ) as pbar:
                        for chunk in response.iter_content(
                            chunk_size=8192
                        ):
                            f.write(chunk)
                            pbar.update(len(chunk))
                else:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            # Проверяем, что файл не пустой
            if filepath.stat().st_size < 1000:
                logger.warning(
                    f"Скачанный файл слишком маленький: "
                    f"{filepath.stat().st_size} байт"
                )
                filepath.unlink()
                return None

            # Проверяем PDF-заголовок
            with open(filepath, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    logger.warning(
                        f"Файл не является PDF: {filepath.name}"
                    )
                    filepath.unlink()
                    return None

            logger.info(
                f"PDF скачан: {filepath.name} "
                f"({filepath.stat().st_size / 1024:.1f} КБ)"
            )
            return str(filepath)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка скачивания PDF: {e}")
            if filepath.exists():
                filepath.unlink()
            return None
        except IOError as e:
            logger.error(f"Ошибка записи файла: {e}")
            return None