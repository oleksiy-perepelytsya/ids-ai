"""Telegram adapter — implements InterfaceAdapter for the Telegram transport.

This is a thin layer that translates between python-telegram-bot objects
and the transport-agnostic ``Message`` / ``Reply`` types used by the
core ``CommandHandler``.
"""

from __future__ import annotations

from typing import Optional
import io

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler as TGCommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ids.interfaces.base import (
    Attachment,
    InterfaceAdapter,
    Message,
    MessageFormat,
    ProgressCallback,
    Reply,
    UserContext,
)
from ids.interfaces.command_handler import CommandHandler
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


def _buttons_to_markup(buttons: list[list]) -> Optional[InlineKeyboardMarkup]:
    """Convert generic Button rows into a Telegram InlineKeyboardMarkup."""
    if not buttons:
        return None
    rows = []
    for row in buttons:
        rows.append([InlineKeyboardButton(btn.label, callback_data=btn.callback_data) for btn in row])
    return InlineKeyboardMarkup(rows)


def _extract_urls(message) -> list[str]:
    if not message.entities:
        return []
    urls: list[str] = []
    text = message.text or ""
    for entity in message.entities:
        if entity.type == "url":
            urls.append(text[entity.offset: entity.offset + entity.length])
        elif entity.type == "text_link" and entity.url:
            urls.append(entity.url)
    return urls


def _is_url_only(message, urls: list[str]) -> bool:
    if not urls:
        return False
    remainder = message.text or ""
    for entity in (message.entities or []):
        if entity.type == "url":
            url_text = (message.text or "")[entity.offset: entity.offset + entity.length]
            remainder = remainder.replace(url_text, "", 1)
    return remainder.strip() == ""


class TelegramAdapter(InterfaceAdapter):
    """Telegram transport adapter."""

    def __init__(self) -> None:
        self._app: Optional[Application] = None
        self._handler: Optional[CommandHandler] = None

    def set_handler(self, handler: CommandHandler) -> None:
        self._handler = handler

    # -- InterfaceAdapter implementation -----------------------------------

    async def send(self, chat_id: int, reply: Reply) -> None:
        if not self._app:
            return
        parse_mode = ParseMode.MARKDOWN if reply.format == MessageFormat.MARKDOWN else None
        markup = _buttons_to_markup(reply.buttons)

        # edit_message is only possible when we have the original message —
        # in practice the Telegram handlers call query.edit_message_text directly.
        # Here we fall back to sending a new message.
        await self._app.bot.send_message(
            chat_id=chat_id,
            text=reply.text,
            parse_mode=parse_mode,
            reply_markup=markup,
        )

    async def send_file(self, chat_id: int, attachment: Attachment,
                        caption: str = "") -> None:
        if not self._app:
            return
        file_obj = io.BytesIO(attachment.data)
        file_obj.name = attachment.filename
        await self._app.bot.send_document(
            chat_id=chat_id,
            document=file_obj,
            filename=attachment.filename,
            caption=caption,
        )

    async def show_typing(self, chat_id: int) -> None:
        if self._app:
            await self._app.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    def is_authorized(self, user: UserContext) -> bool:
        return user.user_id in settings.get_allowed_users()

    def make_progress_callback(self, chat_id: int) -> ProgressCallback:
        async def _cb(msg_text: str) -> None:
            await self.send(chat_id, Reply(text=msg_text, format=MessageFormat.MARKDOWN))
        return _cb

    async def start(self) -> None:
        if not self._app:
            raise RuntimeError("TelegramAdapter: build_app() must be called before start()")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        logger.info("telegram_bot_running")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    # -- Telegram-specific setup -------------------------------------------

    def build_app(self) -> Application:
        """Create and configure the python-telegram-bot Application.

        Registers thin wrapper handlers that convert Telegram objects into
        ``Message`` instances and delegate to the core ``CommandHandler``.
        """
        self._app = Application.builder().token(settings.telegram_bot_token).build()
        h = self._handler
        assert h is not None, "set_handler() must be called before build_app()"

        # Command handlers — one per command
        COMMANDS = [
            "start", "help", "register_project", "list_projects", "project",
            "project_info", "set_prompts", "genprompt", "list_prompts",
            "set_model", "set_rounds", "delete_project", "status", "history",
            "cancel", "export", "sourcer", "learn", "code", "analyze",
            "validate", "daily_update",
        ]
        for cmd in COMMANDS:
            handler_fn = self._make_command_wrapper(cmd)
            self._app.add_handler(TGCommandHandler(cmd, handler_fn))

        not_edited = ~filters.UpdateType.EDITED_MESSAGE

        # Text messages → handle_message
        self._app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & not_edited,
            self._wrap_message,
        ))

        # Documents → handle_document
        self._app.add_handler(MessageHandler(
            filters.Document.ALL & not_edited,
            self._wrap_document,
        ))

        # Callbacks
        self._app.add_handler(CallbackQueryHandler(self._wrap_callback))

        # Unknown commands (must be last)
        self._app.add_handler(MessageHandler(
            filters.COMMAND & not_edited,
            self._wrap_unknown_command,
        ))

        # Error handler
        self._app.add_error_handler(_error_handler)

        token_prefix = (settings.telegram_bot_token or "")[:10]
        logger.info("telegram_bot_created", bot_token=token_prefix + "...")
        return self._app

    # -- Wrappers (Telegram → Message) -------------------------------------

    def _make_command_wrapper(self, cmd_name: str):
        """Return an async handler function for the given command."""
        async def _wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            msg = _update_to_message(update, context)
            msg.command = cmd_name
            handler_fn = getattr(self._handler, f"cmd_{cmd_name}", None)
            if handler_fn:
                await handler_fn(msg)
        return _wrapper

    async def _wrap_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = _update_to_message(update, context)
        await self._handler.handle_message(msg)

    async def _wrap_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        doc = update.message.document
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        msg = _update_to_message(update, context)
        msg.attachments = [Attachment(
            filename=doc.file_name or "unnamed_file",
            data=bytes(file_bytes),
        )]
        await self._handler.handle_document(msg)

    async def _wrap_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user = UserContext(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            username=update.effective_user.username,
            raw=update,
        )
        msg = Message(
            text=query.data or "",
            user=user,
            callback_data=query.data,
            raw=query,
        )
        await self._handler.handle_callback(msg)

    async def _wrap_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = _update_to_message(update, context)
        await self._handler.handle_unknown_command(msg)


# -- Helpers ---------------------------------------------------------------

def _update_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Message:
    """Convert a Telegram Update into a generic Message."""
    user = UserContext(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        username=update.effective_user.username,
        raw=update,
    )
    text = update.message.text or ""
    urls = _extract_urls(update.message)
    return Message(
        text=text,
        user=user,
        args=list(context.args or []),
        urls=urls,
        is_url_only=_is_url_only(update.message, urls),
        raw=update.message,
    )


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    logger.error("unhandled_handler_error", error=str(error), exc_info=error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"❌ Internal error ({type(error).__name__}): {str(error)[:400]}"
            )
        except Exception:
            pass
