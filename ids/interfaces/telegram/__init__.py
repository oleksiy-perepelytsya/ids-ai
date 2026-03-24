"""Telegram interface module.

Provides both the legacy ``create_bot`` factory (used by ``__main__``)
and the new ``TelegramAdapter`` implementing ``InterfaceAdapter``.
"""

from .bot import create_bot
from .adapter import TelegramAdapter
from .handlers import TelegramHandlers
from .formatters import TelegramFormatter
from .keyboards import TelegramKeyboards

__all__ = [
    "create_bot",
    "TelegramAdapter",
    "TelegramHandlers",
    "TelegramFormatter",
    "TelegramKeyboards",
]
