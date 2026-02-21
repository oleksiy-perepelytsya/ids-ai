"""Telegram bot initialization and setup"""

from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from ids.orchestrator import SessionManager
from ids.orchestrator.code_workflow import CodeWorkflow
from ids.storage import MongoProjectStore
from ids.interfaces.telegram.handlers import TelegramHandlers
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Surface unhandled handler exceptions to the user instead of silently discarding them."""
    error = context.error
    logger.error("unhandled_handler_error", error=str(error), exc_info=error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"❌ Internal error ({type(error).__name__}): {str(error)[:400]}"
            )
        except Exception:
            pass


def create_bot(
    session_manager: SessionManager,
    project_store: MongoProjectStore,
    code_workflow: Optional[CodeWorkflow] = None,
) -> Application:
    """
    Create and configure Telegram bot application.

    Args:
        session_manager: Session manager for deliberation
        project_store: Project storage
        code_workflow: Code workflow for implementation

    Returns:
        Configured Application ready to run
    """
    # Create application
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Create handlers instance
    handlers = TelegramHandlers(session_manager, project_store, code_workflow)

    # Register command handlers
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("register_project", handlers.cmd_register_project))
    app.add_handler(CommandHandler("list_projects", handlers.cmd_list_projects))
    app.add_handler(CommandHandler("project", handlers.cmd_project))
    app.add_handler(CommandHandler("project_info", handlers.cmd_project_info))
    app.add_handler(CommandHandler("set_prompts", handlers.cmd_set_prompts))
    app.add_handler(CommandHandler("delete_project", handlers.cmd_delete_project))
    app.add_handler(CommandHandler("status", handlers.cmd_status))
    app.add_handler(CommandHandler("history", handlers.cmd_history))
    app.add_handler(CommandHandler("cancel", handlers.cmd_cancel))
    app.add_handler(CommandHandler("export", handlers.cmd_export))
    app.add_handler(CommandHandler("sourcer", handlers.cmd_sourcer))
    app.add_handler(CommandHandler("learn", handlers.cmd_learn))
    app.add_handler(CommandHandler("code", handlers.cmd_code))
    app.add_handler(CommandHandler("analyze", handlers.cmd_analyze))
    app.add_handler(CommandHandler("validate", handlers.cmd_validate))

    # Register message handler (for task submission)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handlers.handle_message
    ))

    # Register callback query handler (for inline buttons)
    app.add_handler(CallbackQueryHandler(handlers.handle_callback))

    # Register error handler — surfaces all handler exceptions to the user
    app.add_error_handler(_error_handler)

    logger.info("telegram_bot_created", bot_token=settings.telegram_bot_token[:10] + "...")

    return app
