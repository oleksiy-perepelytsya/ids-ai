"""IDS Interface abstractions.

Provides a protocol-based adapter layer so the core business logic
(command handling, deliberation orchestration) is decoupled from the
transport mechanism (Telegram, CLI, Web, MCP, WhatsApp, etc.).
"""

from .base import InterfaceAdapter, Message, UserContext, Attachment

__all__ = [
    "InterfaceAdapter",
    "Message",
    "UserContext",
    "Attachment",
]
