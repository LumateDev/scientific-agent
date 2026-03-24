"""
Модуль перевода текстов.

Поддерживает:
- Google Translate (через deep-translator, бесплатный)
- Заглушка (без перевода) — для работы без интернета

Используется для перевода аннотаций на русский язык.
"""

import logging
from typing import Optional

from config import Config

logger = logging.getLogger("sci_agent.translator")


class Translator:
    """
    Переводчик текстов с определением языка.
    
    Основной сценарий: перевод английских аннотаций статей
    на русский язык для удобства исследователя.
    """

    def __init__(self):
        self.method = Config.TRANSLATOR
        self._translator = None
        self._init_translator()

    def _init_translator(self):
        """Инициализация движка перевода."""
        if self.method == "google":
            try:
                from deep_translator import GoogleTranslator
                self._translator = GoogleTranslator(
                    source='en', target='ru'
                )
                logger.info("Переводчик Google Translate инициализирован")
            except ImportError:
                logger.warning(
                    "deep-translator не установлен. "
                    "pip install deep-translator"
                )
                self.method = "none"
            except Exception as e:
                logger.warning(f"Ошибка инициализации переводчика: {e}")
                self.method = "none"
        elif self.method == "none":
            logger.info("Перевод отключён")

    def translate(
        self,
        text: str,
        source: str = "en",
        target: str = "ru"
    ) -> str:
        """
        Перевод текста.
        
        Args:
            text: Исходный текст
            source: Язык источника
            target: Целевой язык
            
        Returns:
            Переведённый текст или исходный при ошибке
        """
        if not text or not text.strip():
            return ""

        # Если текст уже на целевом языке — не переводим
        if source == target:
            return text

        if self.method == "none":
            return text

        try:
            if self.method == "google":
                return self._translate_google(text, source, target)
        except Exception as e:
            logger.warning(f"Ошибка перевода: {e}")
            return text

        return text

    def _translate_google(
        self, text: str, source: str, target: str
    ) -> str:
        """Перевод через Google Translate."""
        from deep_translator import GoogleTranslator

        # Google Translate имеет лимит 5000 символов
        max_chars = 4500

        if len(text) <= max_chars:
            translator = GoogleTranslator(source=source, target=target)
            result = translator.translate(text)
            return result if result else text

        # Длинный текст — разбиваем на части по предложениям
        sentences = text.replace('. ', '.\n').split('\n')
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_chars:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        # Переводим каждый чанк
        translated_parts = []
        translator = GoogleTranslator(source=source, target=target)
        for chunk in chunks:
            try:
                translated = translator.translate(chunk)
                translated_parts.append(translated if translated else chunk)
            except Exception as e:
                logger.warning(f"Ошибка перевода чанка: {e}")
                translated_parts.append(chunk)

        return " ".join(translated_parts)

    def is_russian(self, text: str) -> bool:
        """
        Определение, написан ли текст на русском.
        Простая эвристика: проверяем долю кириллических символов.
        """
        if not text:
            return False
        cyrillic_count = sum(
            1 for c in text if '\u0400' <= c <= '\u04FF'
        )
        total_alpha = sum(1 for c in text if c.isalpha())
        if total_alpha == 0:
            return False
        return (cyrillic_count / total_alpha) > 0.5