"""Telegram bot initialization and setup"""

from typing import Optional

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from ids.orchestrator import SessionManager
from ids.orchestrator.code_workflow import CodeWorkflow
from ids.storage import MongoProjectStore
from ids.interfaces.telegram.handlers import TelegramHandlers
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


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
    app.add_handler(CommandHandler("status", handlers.cmd_status))
    app.add_handler(CommandHandler("history", handlers.cmd_history))
    app.add_handler(CommandHandler("cancel", handlers.cmd_cancel))
    app.add_handler(CommandHandler("export", handlers.cmd_export))
    app.add_handler(CommandHandler("sourcer", handlers.cmd_sourcer))
    app.add_handler(CommandHandler("learn", handlers.cmd_learn))
    
    # Register message handler (for task submission)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handlers.handle_message
    ))
    
    # Register callback query handler (for inline buttons)
    app.add_handler(CallbackQueryHandler(handlers.handle_callback))
    
    logger.info("telegram_bot_created", bot_token=settings.telegram_bot_token[:10] + "...")
    
    return app
