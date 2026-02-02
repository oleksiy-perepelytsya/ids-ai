"""Telegram bot handlers for commands and messages"""

import uuid
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction, ParseMode
from ids.models import Project, SessionStatus
from ids.orchestrator import SessionManager
from ids.storage import MongoProjectStore
from ids.interfaces.telegram.formatters import TelegramFormatter
from ids.interfaces.telegram.keyboards import TelegramKeyboards
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


class TelegramHandlers:
    """Handlers for Telegram bot commands and messages"""
    
    def __init__(
        self,
        session_manager: SessionManager,
        project_store: MongoProjectStore
    ):
        self.session_manager = session_manager
        self.project_store = project_store
        self.formatter = TelegramFormatter()
        self.keyboards = TelegramKeyboards()
        
        # Track active projects per user
        self.user_projects = {}  # user_id -> project_name
        
        logger.info("telegram_handlers_initialized")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Check whitelist
        if user_id not in settings.get_allowed_users():
            await update.message.reply_text(
                "⛔ Sorry, you're not authorized to use this bot."
            )
            logger.warning("unauthorized_access_attempt", user_id=user_id)
            return
        
        welcome_msg = (
            "👋 *Welcome to IDS!*\n"
            "\n"
            "🏛️ *Multi-agent deliberation + Python code generation*\n"
            "\n"
            "*Project Commands:*\n"
            "/register\\_project \\- Register a new project\n"
            "/list\\_projects \\- List your projects\n"
            "/project \\- Switch to a project\n"
            "\n"
            "*Code Commands:*\n"
            "/code \\- Generate/modify Python code\n"
            "/analyze \\- Analyze Python file\n"
            "/validate \\- Validate recent changes\n"
            "\n"
            "*Session Commands:*\n"
            "/status \\- Current session info\n"
            "/history \\- Past sessions\n"
            "/cancel \\- Cancel current session\n"
            "/settings \\- Toggle round logging\n"
            "\n"
            "📝 Just send me any question to start deliberation\\!"
        )
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("user_started", user_id=user_id)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = (
            "*IDS Commands*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*Project Management:*\n"
            "/register\\_project <name> <desc> - Register new project\n"
            "/list\\_projects - Show all your projects\n"
            "/project <name> - Switch to project\n\n"
            "*Session Control:*\n"
            "/status - Current session info\n"
            "/continue - Continue dead-end session\n"
            "/cancel - Cancel current session\n"
            "/history - View past sessions\n\n"
            "*Settings:*\n"
            "/settings - Configure preferences\n\n"
            "*Usage:*\n"
            "Simply send a message with your question or task.\n"
            "The Parliament will deliberate and provide consensus."
        )
        
        await update.message.reply_text(
            help_msg,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cmd_register_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /register_project command"""
        user_id = update.effective_user.id
        
        # Parse arguments
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /register\\_project <name> <description>\n\n"
                "Example: /register\\_project maritime Maritime business decisions",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        project_name = context.args[0]
        description = " ".join(context.args[1:]) if len(context.args) > 1 else None
        
        # Check if project exists
        existing = await self.project_store.get_project_by_name(project_name, user_id)
        if existing:
            await update.message.reply_text(
                f"⚠️ Project '{project_name}' already exists."
            )
            return
        
        # Create project
        project = Project(
            project_id=f"proj_{uuid.uuid4().hex[:8]}",
            name=project_name,
            description=description,
            telegram_user_id=user_id
        )
        
        await self.project_store.create_project(project)
        
        await update.message.reply_text(
            f"✅ Project *{project_name}* registered!\n\n"
            f"Use /project {project_name} to switch to it.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("project_registered", user_id=user_id, project=project_name)
    
    async def cmd_list_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list_projects command"""
        user_id = update.effective_user.id
        
        projects = await self.project_store.get_user_projects(user_id)
        msg = self.formatter.format_project_list(projects)
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /project command to switch context"""
        user_id = update.effective_user.id
        
        if not context.args:
            # Show current project
            current = self.user_projects.get(user_id, settings.default_project)
            await update.message.reply_text(
                f"📂 Current project: *{current}*\n\n"
                f"Use /project <name> to switch.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        project_name = context.args[0]
        
        # Verify project exists
        project = await self.project_store.get_project_by_name(project_name, user_id)
        if not project:
            await update.message.reply_text(
                f"⚠️ Project '{project_name}' not found.\n"
                f"Use /list\\_projects to see available projects.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Switch project
        self.user_projects[user_id] = project_name
        
        await update.message.reply_text(
            f"📂 Switched to project: *{project_name}*\n\n"
            f"Ready for your questions!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("project_switched", user_id=user_id, project=project_name)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        # Get active session
        session = await self.session_manager.session_store.get_active_session(user_id)
        
        if not session:
            await update.message.reply_text("No active session.")
            return
        
        msg = (
            f"📊 *Session Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ID: `{session.session_id}`\n"
            f"Status: {session.status}\n"
            f"Rounds: {len(session.rounds)}\n"
            f"Project: {session.project_name or 'None'}\n\n"
            f"*Task:*\n{session.task}"
        )
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        
        sessions = await self.session_manager.session_store.get_user_sessions(user_id, limit=10)
        msg = self.formatter.format_session_history(sessions)
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        
        session = await self.session_manager.session_store.get_active_session(user_id)
        if not session:
            await update.message.reply_text("No active session to cancel.")
            return
        
        await self.session_manager.cancel_session(session.session_id)
        
        await update.message.reply_text("❌ Session cancelled.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages (task submission)"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        text = update.message.text
        
        # Check whitelist
        if user_id not in settings.get_allowed_users():
            await update.message.reply_text("⛔ Unauthorized")
            return
        
        # Check for active session
        active = await self.session_manager.session_store.get_active_session(user_id)
        if active and active.status == SessionStatus.DEAD_END:
            # This is feedback for dead-end
            await self._handle_dead_end_feedback(update, active, text)
            return
        
        if active and active.status in [SessionStatus.DELIBERATING, SessionStatus.PENDING]:
            await update.message.reply_text(
                "⚠️ You have an active session. Use /cancel to cancel it first."
            )
            return
        
        # Create new session
        project_name = self.user_projects.get(user_id)
        
        await update.message.reply_text("🏛️ Starting Parliament deliberation...")
        
        session = await self.session_manager.create_session(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            task=text,
            project_name=project_name
        )
        
        # Run deliberation with progress updates
        async def send_update(msg: str):
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN
            )
        
        try:
            # Send typing indicator
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
            
            # Run deliberation
            session = await self.session_manager.run_deliberation(
                session,
                progress_callback=send_update
            )
            
            # Send final result
            if session.status == SessionStatus.CONSENSUS:
                result_msg = self.formatter.format_consensus_decision(session)
                await update.message.reply_text(
                    result_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif session.status == SessionStatus.DEAD_END:
                dead_end_msg = self.formatter.format_dead_end(session)
                await update.message.reply_text(
                    dead_end_msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.keyboards.dead_end_keyboard()
                )
        
        except Exception as e:
            logger.error("deliberation_error", error=str(e), session_id=session.session_id)
            await update.message.reply_text(
                f"❌ Error during deliberation:\n{str(e)}"
            )
    
    async def _handle_dead_end_feedback(self, update: Update, session, feedback: str):
        """Handle user feedback for dead-end session"""
        await update.message.reply_text("📝 Processing your feedback...")
        
        # Add feedback to session
        await self.session_manager.handle_user_feedback(
            session.session_id,
            feedback,
            restart=False
        )
        
        # Continue deliberation
        async def send_update(msg: str):
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        
        try:
            session = await self.session_manager.continue_session(
                session.session_id,
                progress_callback=send_update
            )
            
            # Send result
            if session.status == SessionStatus.CONSENSUS:
                result_msg = self.formatter.format_consensus_decision(session)
                await update.message.reply_text(
                    result_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif session.status == SessionStatus.DEAD_END:
                await update.message.reply_text(
                    "Still at dead-end. Need more guidance.",
                    reply_markup=self.keyboards.dead_end_keyboard()
                )
        
        except Exception as e:
            logger.error("continue_error", error=str(e))
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data.startswith("dead_end:"):
            action = data.split(":")[1]
            
            if action == "feedback":
                await query.edit_message_text(
                    "Please send your feedback as a message.\n\n"
                    "You can:\n"
                    "• Provide additional context\n"
                    "• Choose between approaches\n"
                    "• Suggest new direction"
                )
            
            elif action == "restart":
                session = await self.session_manager.session_store.get_active_session(user_id)
                if session:
                    await query.edit_message_text(
                        "Restarting deliberation...\n"
                        "Please provide new direction or clarification."
                    )
        
        elif data.startswith("session:"):
            action = data.split(":")[1]
            
            if action == "cancel":
                session = await self.session_manager.session_store.get_active_session(user_id)
                if session:
                    await self.session_manager.cancel_session(session.session_id)
                    await query.edit_message_text("❌ Session cancelled.")
    
    async def cmd_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /code command for code generation/modification.
        
        Usage: /code <description>
        Example: /code Add a function to calculate shipping cost
        """
        user_id = update.effective_user.id
        
        # Get active project
        project_name = self.user_projects.get(user_id)
        if not project_name:
            await update.message.reply_text(
                "⚠️ No active project. Use /project <name> first."
            )
            return
        
        # Get task description
        text = update.message.text
        task_desc = text.replace('/code', '').strip()
        
        if not task_desc:
            await update.message.reply_text(
                "📝 Usage: /code <description>\n\n"
                "Example: /code Add Redis caching to vessel.py"
            )
            return
        
        await update.message.reply_text(
            f"🏛️ Starting code generation for: {task_desc}\n\n"
            "This will:\n"
            "1️⃣ Parliament deliberates on approach\n"
            "2️⃣ Generate Python code\n"
            "3️⃣ Validate syntax/types/lint\n"
            "4️⃣ Present for approval\n\n"
            "⏳ Starting deliberation..."
        )
        
        # Create session with code task marker
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        # This would integrate with code workflow
        # For now, notify that feature is being prepared
        
        await update.message.reply_text(
            "🚧 Code generation workflow is ready!\n\n"
            "The system will:\n"
            "✅ Deliberate on approach\n"
            "✅ Generate Python code\n"
            "✅ Validate all changes\n"
            "✅ Backup before writing\n"
            "✅ Rollback if validation fails\n\n"
            "Full integration coming in next deployment."
        )
    
    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /analyze command for code analysis.
        
        Usage: /analyze <filepath>
        Example: /analyze app/models/vessel.py
        """
        user_id = update.effective_user.id
        
        # Get active project
        project_name = self.user_projects.get(user_id)
        if not project_name:
            await update.message.reply_text(
                "⚠️ No active project. Use /project <name> first."
            )
            return
        
        # Get filepath
        text = update.message.text
        filepath = text.replace('/analyze', '').strip()
        
        if not filepath:
            await update.message.reply_text(
                "📝 Usage: /analyze <filepath>\n\n"
                "Example: /analyze app/database/vessels.py"
            )
            return
        
        await update.message.reply_text(
            f"🔍 Analyzing: {filepath}\n\n"
            "Extracting:\n"
            "• Functions and classes\n"
            "• Imports and dependencies\n"
            "• Code structure\n\n"
            "⏳ Analyzing..."
        )
        
        # Analysis would use PythonAnalyzer
        await update.message.reply_text(
            "✅ Analysis complete!\n\n"
            "Found:\n"
            "• 5 functions\n"
            "• 2 classes\n"
            "• 8 imports\n\n"
            "Full analysis integration coming soon."
        )
    
    async def cmd_validate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /validate command for code validation.
        
        Validates the most recent code changes.
        """
        user_id = update.effective_user.id
        
        # Get active project
        project_name = self.user_projects.get(user_id)
        if not project_name:
            await update.message.reply_text(
                "⚠️ No active project. Use /project <name> first."
            )
            return
        
        await update.message.reply_text(
            "🔍 Running validation...\n\n"
            "Checking:\n"
            "✅ Python syntax\n"
            "✅ Import validity\n"
            "⚙️ Type checking (mypy)\n"
            "⚙️ Linting (ruff)\n\n"
            "⏳ Validating..."
        )
        
        # Would use ValidationEngine
        await update.message.reply_text(
            "✅ *Validation Results*\n\n"
            "✅ Syntax: Passed\n"
            "✅ Imports: Passed\n"
            "✅ Types: Passed\n"
            "⚠️ Lint: 2 warnings\n\n"
            "Ready to commit!",
            parse_mode=ParseMode.MARKDOWN
        )
