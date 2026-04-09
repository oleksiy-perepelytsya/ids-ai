"""Abstract interface adapter for IDS.

Any transport (Telegram, CLI, Web, MCP, WhatsApp, Viber, Email, etc.)
implements ``InterfaceAdapter`` so the core command handler can
communicate with users without knowing the underlying channel.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


# ---------------------------------------------------------------------------
# Lightweight value objects shared across all interfaces
# ---------------------------------------------------------------------------

class MessageFormat(str, Enum):
    """Supported output formats."""
    PLAIN = "plain"
    MARKDOWN = "markdown"


@dataclass
class UserContext:
    """Identity & channel information for the current user interaction.

    Every interface populates this from its own primitives (e.g. Telegram
    ``Update``, HTTP request, stdin) so the command handler never needs to
    import transport-specific types.
    """
    user_id: int
    chat_id: int
    username: Optional[str] = None
    raw: Any = None  # original transport object (Update, Request, …)


@dataclass
class Attachment:
    """A file the user sent or we want to send back."""
    filename: str
    data: bytes
    mime_type: Optional[str] = None


@dataclass
class Message:
    """An incoming message from any interface."""
    text: str
    user: UserContext
    command: Optional[str] = None        # e.g. "start", "help", "project"
    args: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    is_url_only: bool = False
    callback_data: Optional[str] = None  # inline-button / selection payload
    raw: Any = None                      # original transport message


# ---------------------------------------------------------------------------
# Action descriptors returned by the command handler
# ---------------------------------------------------------------------------

@dataclass
class Button:
    """A single interactive button."""
    label: str
    callback_data: str


@dataclass
class Reply:
    """Something the command handler wants to send back to the user.

    The interface adapter is responsible for translating this into whatever
    the transport supports (Telegram message, terminal print, HTTP response…).
    """
    text: str
    format: MessageFormat = MessageFormat.MARKDOWN
    buttons: list[list[Button]] = field(default_factory=list)  # rows of buttons
    file: Optional[Attachment] = None
    edit_message: bool = False  # replace previous message (for callbacks)


# ---------------------------------------------------------------------------
# Progress / typing callback
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------

class InterfaceAdapter(abc.ABC):
    """Contract that every transport layer must implement.

    The adapter is the *only* place where transport-specific imports live.
    The core command handler calls these methods exclusively.
    """

    # -- sending -----------------------------------------------------------

    @abc.abstractmethod
    async def send(self, chat_id: int, reply: Reply) -> None:
        """Deliver a reply to the given chat/channel."""

    @abc.abstractmethod
    async def send_file(self, chat_id: int, attachment: Attachment,
                        caption: str = "") -> None:
        """Send a file/document to the given chat/channel."""

    @abc.abstractmethod
    async def show_typing(self, chat_id: int) -> None:
        """Indicate that the bot is "working" (typing indicator, spinner…)."""

    # -- auth --------------------------------------------------------------

    @abc.abstractmethod
    def is_authorized(self, user: UserContext) -> bool:
        """Return True if the user is allowed to interact."""

    # -- lifecycle ---------------------------------------------------------

    @abc.abstractmethod
    async def start(self) -> None:
        """Start listening for messages (polling, HTTP server, stdin…)."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Graceful shutdown."""

    # -- helpers (optional overrides) --------------------------------------

    def make_progress_callback(self, chat_id: int) -> ProgressCallback:
        """Return an async callback that sends progress text to the user.

        Default implementation wraps ``self.send`` with MARKDOWN format.
        Subclasses may override for transport-specific typing indicators, etc.
        """
        async def _cb(msg: str) -> None:
            await self.send(chat_id, Reply(text=msg, format=MessageFormat.MARKDOWN))
        return _cb

    def make_keep_typing_task(self, chat_id: int) -> "asyncio.Task[None]":
        """Return a background task that periodically sends a typing indicator.

        Call ``task.cancel()`` when the long operation finishes.
        Default implementation loops ``show_typing`` every 4 seconds.
        """
        async def _loop() -> None:
            try:
                while True:
                    await self.show_typing(chat_id)
                    await asyncio.sleep(4)
            except asyncio.CancelledError:
                pass
        return asyncio.ensure_future(_loop())
