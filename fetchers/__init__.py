"""
Модуль fetchers — источники научных статей.

Каждый источник реализует интерфейс BaseFetcher,
обеспечивая единообразный доступ к разным базам данных.
"""

from .arxiv_fetcher import ArxivFetcher
from .elibrary_fetcher import ElibraryFetcher
from .scopus_fetcher import ScopusFetcher
from .wos_fetcher import WoSFetcher

__all__ = ["ArxivFetcher", "ElibraryFetcher", "ScopusFetcher", "WoSFetcher"]