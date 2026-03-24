"""CLI (terminal REPL) adapter for IDS.

Implements ``InterfaceAdapter`` so the full IDS command set is usable
from a plain terminal — no Telegram, no web server.

Run with:  python -m ids --interface cli
"""

from __future__ import annotations

import asyncio
import shlex
from typing import Optional

from ids.interfaces.base import (
    Attachment,
    InterfaceAdapter,
    Message,
    MessageFormat,
    Reply,
    UserContext,
)
from ids.interfaces.command_handler import CommandHandler
from ids.utils import get_logger

logger = get_logger(__name__)

# The CLI always uses a single virtual user
_CLI_USER_ID = 1
_CLI_CHAT_ID = 1

# ANSI helpers
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"


def _strip_markdown(text: str) -> str:
    """Best-effort conversion of Telegram-flavoured Markdown to terminal text."""
    # Remove escape backslashes added for Telegram
    text = text.replace("\\-", "-").replace("\\.", ".").replace("\\!", "!")
    text = text.replace("\\_", "_").replace("\\*", "*").replace("\\`", "`").replace("\\[", "[")
    return text


def _render_reply(reply: Reply) -> str:
    """Convert a Reply into styled terminal output."""
    text = reply.text
    if reply.format == MessageFormat.MARKDOWN:
        text = _strip_markdown(text)

    lines = [text]

    if reply.buttons:
        lines.append("")
        for row in reply.buttons:
            for btn in row:
                lines.append(f"  {_CYAN}[{btn.callback_data}]{_RESET} {btn.label}")

    return "\n".join(lines)


class CLIAdapter(InterfaceAdapter):
    """Terminal REPL interface for IDS."""

    def __init__(self) -> None:
        self._handler: Optional[CommandHandler] = None
        self._running = False

    def set_handler(self, handler: CommandHandler) -> None:
        self._handler = handler

    # -- InterfaceAdapter implementation -----------------------------------

    async def send(self, chat_id: int, reply: Reply) -> None:
        output = _render_reply(reply)
        print(output)
        print()

    async def send_file(self, chat_id: int, attachment: Attachment,
                        caption: str = "") -> None:
        path = attachment.filename
        with open(path, "wb") as f:
            f.write(attachment.data)
        print(f"{_GREEN}📎 File saved: {path}{_RESET}")
        if caption:
            print(f"   {caption}")
        print()

    async def show_typing(self, chat_id: int) -> None:
        print(f"{_DIM}⏳ Working...{_RESET}")

    def is_authorized(self, user: UserContext) -> bool:
        # CLI is always authorized — it's local
        return True

    async def start(self) -> None:
        """Run the interactive REPL loop."""
        if not self._handler:
            raise RuntimeError("CLIAdapter: set_handler() must be called before start()")

        self._running = True
        user = UserContext(user_id=_CLI_USER_ID, chat_id=_CLI_CHAT_ID)

        print(f"\n{_BOLD}IDS — Interactive Deliberation System (CLI){_RESET}")
        print(f"{_DIM}Type /help for commands, Ctrl+C to exit.{_RESET}\n")

        while self._running:
            try:
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input(f"{_GREEN}ids>{_RESET} ")
                )
            except (EOFError, KeyboardInterrupt):
                print(f"\n{_DIM}Bye!{_RESET}")
                break

            raw = raw.strip()
            if not raw:
                continue

            msg = self._parse_input(raw, user)

            try:
                if msg.command:
                    handler_method = getattr(self._handler, f"cmd_{msg.command}", None)
                    if handler_method:
                        await handler_method(msg)
                    else:
                        await self._handler.handle_unknown_command(msg)
                else:
                    await self._handler.handle_message(msg)
            except Exception as e:
                print(f"{_RED}❌ Error: {e}{_RESET}\n")
                logger.error("cli_command_error", error=str(e), exc_info=True)

    async def stop(self) -> None:
        self._running = False

    # -- Internal ----------------------------------------------------------

    @staticmethod
    def _parse_input(raw: str, user: UserContext) -> Message:
        """Parse a raw input line into a ``Message``."""
        if raw.startswith("/"):
            parts = raw.split(maxsplit=1)
            command = parts[0][1:]  # strip leading /
            args_str = parts[1] if len(parts) > 1 else ""
            # Handle callback syntax: /callback:<data>
            if raw.startswith("/callback:"):
                return Message(
                    text=raw,
                    user=user,
                    callback_data=raw[len("/callback:"):],
                )
            try:
                args = shlex.split(args_str)
            except ValueError:
                args = args_str.split()
            return Message(
                text=raw,
                user=user,
                command=command,
                args=args,
            )
        else:
            return Message(text=raw, user=user)
