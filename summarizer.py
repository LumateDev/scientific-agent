"""
Модуль суммаризации научных текстов.

Реализует экстрактивную суммаризацию — выбор наиболее
важных предложений из текста на основе частотности
ключевых слов и позиции предложения.

Используется библиотека sumy для основного метода,
с фоллбэком на простую частотную суммаризацию.
"""

import re
import logging
from typing import List, Optional

from config import Config

logger = logging.getLogger("sci_agent.summarizer")


class Summarizer:
    """
    Экстрактивный суммаризатор научных текстов.
    
    Методы:
    1. sumy (LsaSummarizer) — основной метод, на основе LSA
    2. frequency — простой частотный метод (фоллбэк)
    
    Для научных текстов экстрактивная суммаризация подходит
    хорошо, так как ключевые выводы обычно содержатся в
    конкретных предложениях.
    """

    def __init__(self):
        self.method = Config.SUMMARIZER
        self.num_sentences = Config.SUMMARY_SENTENCES
        self._init_sumy()

    def _init_sumy(self):
        """Инициализация sumy и NLTK данных."""
        self._sumy_available = False
        try:
            import nltk
            # Скачиваем необходимые данные NLTK (тихо)
            for resource in ['punkt', 'punkt_tab', 'stopwords']:
                try:
                    nltk.data.find(f'tokenizers/{resource}')
                except LookupError:
                    try:
                        nltk.download(resource, quiet=True)
                    except Exception:
                        pass

            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.lsa import LsaSummarizer
            from sumy.nlp.stemmers import Stemmer
            from sumy.utils import get_stop_words

            self._sumy_available = True
            logger.info("Суммаризатор sumy инициализирован")

        except ImportError:
            logger.warning(
                "sumy не установлен. "
                "Используется простой частотный метод. "
                "pip install sumy nltk"
            )
        except Exception as e:
            logger.warning(f"Ошибка инициализации sumy: {e}")

    def summarize(
        self,
        text: str,
        num_sentences: int = None,
        language: str = "english"
    ) -> str:
        """
        Создание краткого резюме текста.
        
        Args:
            text: Исходный текст (аннотация или полный текст)
            num_sentences: Количество предложений в резюме
            language: Язык текста (english/russian)
            
        Returns:
            Текст резюме
        """
        if not text or len(text.strip()) < 50:
            return text

        num_sentences = num_sentences or self.num_sentences

        # Определяем язык
        if self._is_russian(text):
            language = "russian"

        # Пробуем sumy
        if self._sumy_available:
            try:
                result = self._summarize_sumy(text, num_sentences, language)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Ошибка sumy: {e}")

        # Фоллбэк на простой метод
        return self._summarize_frequency(text, num_sentences)

    def _summarize_sumy(
        self, text: str, num_sentences: int, language: str
    ) -> str:
        """Суммаризация через sumy (LSA метод)."""
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lsa import LsaSummarizer
        from sumy.nlp.stemmers import Stemmer
        from sumy.utils import get_stop_words

        try:
            # Для русского языка
            lang = "russian" if language == "russian" else "english"

            parser = PlaintextParser.from_string(
                text, Tokenizer(lang)
            )

            stemmer = Stemmer(lang)
            summarizer = LsaSummarizer(stemmer)
            summarizer.stop_words = get_stop_words(lang)

            sentences = summarizer(
                parser.document, num_sentences
            )

            summary = " ".join(str(s) for s in sentences)
            return summary

        except Exception as e:
            logger.warning(f"Ошибка LSA суммаризации: {e}")
            return ""

    def _summarize_frequency(
        self, text: str, num_sentences: int
    ) -> str:
        """
        Простая частотная суммаризация.
        
        Алгоритм:
        1. Разбиваем текст на предложения
        2. Подсчитываем частоту слов (без стоп-слов)
        3. Оцениваем каждое предложение по сумме частот его слов
        4. Бонус за позицию: первое и последнее предложения важнее
        5. Выбираем топ-N предложений
        """
        # Стоп-слова (базовый набор для английского и русского)
        stop_words = {
            # English
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'shall', 'can', 'need', 'dare', 'ought',
            'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
            'by', 'from', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between',
            'out', 'off', 'over', 'under', 'again', 'further',
            'then', 'once', 'and', 'but', 'or', 'nor', 'not',
            'so', 'yet', 'both', 'either', 'neither', 'each',
            'every', 'all', 'any', 'few', 'more', 'most',
            'other', 'some', 'such', 'no', 'only', 'own',
            'same', 'than', 'too', 'very', 'just', 'because',
            'if', 'when', 'where', 'how', 'what', 'which',
            'who', 'whom', 'this', 'that', 'these', 'those',
            'it', 'its', 'we', 'our', 'they', 'their', 'he',
            'she', 'him', 'her', 'my', 'your',
            # Russian
            'и', 'в', 'на', 'с', 'по', 'для', 'из', 'к', 'о',
            'от', 'до', 'за', 'при', 'не', 'но', 'а', 'что',
            'как', 'это', 'так', 'его', 'её', 'их', 'уже',
            'или', 'бы', 'же', 'ли', 'да', 'нет', 'был',
            'была', 'было', 'были', 'быть', 'может', 'можно',
            'также', 'более', 'менее', 'между', 'через',
            'после', 'перед', 'под', 'над', 'без', 'около',
        }

        # Разбиваем на предложения
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if len(sentences) <= num_sentences:
            return text

        # Подсчёт частоты слов
        word_freq = {}
        for sentence in sentences:
            words = re.findall(r'\w+', sentence.lower())
            for word in words:
                if word not in stop_words and len(word) > 2:
                    word_freq[word] = word_freq.get(word, 0) + 1

        # Нормализация частот
        max_freq = max(word_freq.values()) if word_freq else 1
        word_freq = {
            w: f / max_freq for w, f in word_freq.items()
        }

        # Оценка предложений
        scored = []
        for i, sentence in enumerate(sentences):
            words = re.findall(r'\w+', sentence.lower())
            score = sum(
                word_freq.get(w, 0) for w in words
            ) / max(len(words), 1)

            # Бонус за позицию (первое и последнее предложения)
            if i == 0:
                score *= 1.5
            elif i == len(sentences) - 1:
                score *= 1.3
            elif i == 1:
                score *= 1.2

            scored.append((i, score, sentence))

        # Выбираем топ предложения, сохраняя порядок
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = sorted(
            scored[:num_sentences],
            key=lambda x: x[0]
        )

        summary = " ".join(s[2] for s in selected)
        return summary

    def _is_russian(self, text: str) -> bool:
        """Определение русского текста."""
        if not text:
            return False
        cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        alpha = sum(1 for c in text if c.isalpha())
        return (cyrillic / max(alpha, 1)) > 0.5