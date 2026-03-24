"""
Модуль управления кэшем.

Обеспечивает кэширование промежуточных результатов
для ускорения повторных запусков.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any

from config import Config

logger = logging.getLogger("sci_agent.cache")


class CacheManager:
    """
    Менеджер кэша с поддержкой TTL (время жизни).
    
    Кэш хранится в JSON-файлах с метаданными о времени создания.
    """

    def __init__(self, cache_dir: Path = None, ttl_hours: int = 24):
        self.cache_dir = cache_dir or Config.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def get(self, key: str) -> Optional[Any]:
        """Получение данных из кэша."""
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем TTL
            created = datetime.fromisoformat(
                data.get("_created", "2000-01-01")
            )
            if datetime.now() - created > self.ttl:
                logger.debug(f"Кэш устарел: {key}")
                cache_file.unlink()
                return None

            return data.get("payload")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Ошибка чтения кэша {key}: {e}")
            return None

    def set(self, key: str, data: Any):
        """Сохранение данных в кэш."""
        cache_file = self.cache_dir / f"{key}.json"
        cache_data = {
            "_created": datetime.now().isoformat(),
            "payload": data
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Кэш сохранён: {key}")

    def clear(self):
        """Очистка всего кэша."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        logger.info(f"Кэш очищен: удалено {count} файлов")

    def stats(self) -> dict:
        """Статистика кэша."""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "files": len(files),
            "total_size_kb": round(total_size / 1024, 1),
            "cache_dir": str(self.cache_dir)
        }