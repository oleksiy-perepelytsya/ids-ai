"""Telegram bot handlers for commands and messages"""

import re
import uuid
from pathlib import Path
from typing import Optional

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction, ParseMode
from ids.models import Project, SessionStatus
from ids.orchestrator import SessionManager
from ids.orchestrator.code_workflow import CodeWorkflow
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
        project_store: MongoProjectStore,
        code_workflow: Optional[CodeWorkflow] = None,
    ):
        self.session_manager = session_manager
        self.project_store = project_store
        self.code_workflow = code_workflow
        self.formatter = TelegramFormatter()
        self.keyboards = TelegramKeyboards()

        # Track active projects per user (user_id -> Project object)
        self.user_projects: dict[int, Project] = {}

        # UI States
        self.awaiting_comment = {}  # user_id -> True
        self.awaiting_learn = {}    # user_id -> True

        logger.info("telegram_handlers_initialized")

    def _get_project(self, user_id: int) -> Optional[Project]:
        """Get the active project for a user."""
        return self.user_projects.get(user_id)

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
            "🏛️ *Multi-agent deliberation platform*\n"
            "\n"
            "*Project Commands:*\n"
            "/register\\_project \\- Register a new project\n"
            "/list\\_projects \\- List your projects\n"
            "/project \\- Switch to a project\n"
            "/project\\_info \\- Show parliament configuration\n"
            "/set\\_prompts \\- Configure parliament agents\n"
            "\n"
            "*Code Commands:*\n"
            "/code \\- Generate/modify code\n"
            "/analyze \\- Analyze a file\n"
            "/validate \\- Validate recent changes\n"
            "\n"
            "*Knowledge Commands:*\n"
            "/learn \\- Add to knowledge base\n"
            "/sourcer \\- Query knowledge base\n"
            "\n"
            "*Session Commands:*\n"
            "/status \\- Current session info\n"
            "/history \\- Past sessions\n"
            "/export \\- Export conversation\n"
            "/cancel \\- Cancel current session\n"
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
            "/project <name> - Switch to project\n"
            "/project\\_info - Show parliament configuration\n"
            "/set\\_prompts <role> <url> - Configure agent prompts\n\n"
            "*Session Control:*\n"
            "/status - Current session info\n"
            "/cancel - Cancel current session\n"
            "/history - View past sessions\n\n"
            "*Knowledge:*\n"
            "/learn [text] - Add text to knowledge base\n"
            "/sourcer <model> <query> - Query knowledge base\n\n"
            "*Usage:*\n"
            "Simply send a question ending with '?' to start deliberation.\n"
            "Any other text is added to the project knowledge base."
        )

        await update.message.reply_text(
            help_msg,
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /learn command"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        if context.args:
            text = " ".join(context.args)
            await self.session_manager.learn_from_text(project.project_id, text)
            await update.message.reply_text(
                f"📝 Added to knowledge base for project: *{project.name}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            self.awaiting_learn[user_id] = True
            await update.message.reply_text(
                "📝 Please send the text you want me to learn and store in the knowledge base."
            )

    async def cmd_sourcer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sourcer command: /sourcer <model> <query>"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "🔍 *Sourcer Mode*\n"
                "Usage: `/sourcer <model> <query>`\n\n"
                "Models: `claude`, `gemini`\n"
                "Example: `/sourcer claude what is the current db schema?`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        model_choice = context.args[0].lower()
        if model_choice not in ["claude", "gemini"]:
            await update.message.reply_text("❌ Invalid model. Use `claude` or `gemini`.")
            return

        query = " ".join(context.args[1:])
        await update.message.reply_text(
            f"🔍 *Sourcer* is analyzing using *{model_choice}*...",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

            response = await self.session_manager.run_sourcer(
                project_id=project.project_id,
                task=query,
                model=model_choice
            )

            msg = [
                f"📝 *Sourcer Response* ({model_choice})\n",
                "━━━━━━━━━━━━━━━━━━━━\n\n",
                response
            ]

            await update.message.reply_text("".join(msg), parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error("sourcer_error", error=str(e))
            await update.message.reply_text(f"❌ Sourcer Error: {str(e)}")

    async def cmd_register_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /register_project command"""
        user_id = update.effective_user.id

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
            f"✅ Project *{project_name}* registered\\!\n\n"
            f"Configure parliament with:\n"
            f"`/set_prompts specialist1 <url>`\n"
            f"`/set_prompts specialist2 <url>`\n"
            f"`/set_prompts generalist <url>` (optional)\n\n"
            f"Use `/project {project_name}` to switch to it\\.",
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
            project = self._get_project(user_id)
            if project:
                await update.message.reply_text(
                    f"📂 Current project: *{project.name}*\n\n"
                    f"Use /project <name> to switch.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "📂 No project selected.\n\n"
                    "Use /project <name> to switch.",
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

        # Switch project (store full Project object)
        self.user_projects[user_id] = project

        specialist_count = len(project.specialist_prompt_urls)
        await update.message.reply_text(
            f"📂 Switched to project: *{project.name}*\n"
            f"Parliament: {specialist_count} specialist(s) configured\n\n"
            f"Ready for your questions!",
            parse_mode=ParseMode.MARKDOWN
        )

        logger.info("project_switched", user_id=user_id, project=project_name, project_id=project.project_id)

    async def cmd_project_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /project_info command - show parliament configuration"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        # Get session count for this project
        sessions = await self.session_manager.session_store.get_user_sessions(
            user_id, project.project_id, limit=100
        )
        session_count = len(sessions)
        last_date = ""
        if sessions:
            last_date = sessions[0].created_at.strftime("%Y-%m-%d")

        # If we have cached agents, show role names too
        agents = self.session_manager._agent_cache.get(project.project_id)

        msg = self.formatter.format_project_info(project, session_count, last_date)

        # Append role names if agents are loaded
        if agents:
            role_lines = []
            for key in sorted(project.specialist_prompt_urls.keys(), key=int):
                role_id = f"specialist_{key}"
                agent = agents.get(role_id)
                if agent:
                    role_lines.append(
                        f"• specialist\\_{key} → *{self.formatter.escape_markdown(agent.role_name)}*"
                    )
            if role_lines:
                msg += "\n*Loaded Role Names:*\n" + "\n".join(role_lines) + "\n"

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_set_prompts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /set_prompts command to configure parliament agent prompts.

        Usage:
            /set_prompts generalist <url>
            /set_prompts sourcer <url>
            /set_prompts specialist1 <url>
            /set_prompts specialist2 <url>
        """
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "*Configure Parliament Prompts*\n\n"
                "Usage: `/set_prompts <role> <url>`\n\n"
                "Roles:\n"
                "• `generalist` — main synthesizer (Claude)\n"
                "• `sourcer` — knowledge retrieval (Gemini)\n"
                "• `specialist1`, `specialist2`, ... — domain experts (Gemini)\n\n"
                "Example:\n"
                "`/set_prompts specialist1 https://raw.githubusercontent.com/.../maritime.md`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        role_arg = context.args[0].lower()
        url = context.args[1]

        # Validate URL is reachable
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http_client:
                async with http_client.head(url, allow_redirects=True) as resp:
                    if resp.status >= 400:
                        # Try GET if HEAD fails
                        async with http_client.get(url, allow_redirects=True) as resp2:
                            if resp2.status >= 400:
                                await update.message.reply_text(
                                    f"❌ URL returned HTTP {resp2.status}. Please check the URL."
                                )
                                return
        except Exception as e:
            await update.message.reply_text(f"❌ Could not reach URL: {str(e)}")
            return

        # Update project model
        # Reload from DB to get latest data
        project = await self.project_store.get_project(project.project_id)

        if role_arg == "generalist":
            project.generalist_prompt_url = url
            role_label = "generalist"
        elif role_arg == "sourcer":
            project.sourcer_prompt_url = url
            role_label = "sourcer"
        elif re.match(r'^specialist(\d+)$', role_arg):
            key = re.match(r'^specialist(\d+)$', role_arg).group(1)
            project.specialist_prompt_urls[key] = url
            role_label = f"specialist_{key}"
        else:
            await update.message.reply_text(
                "❌ Unknown role. Use: `generalist`, `sourcer`, `specialist1`, `specialist2`, ..."
            )
            return

        from datetime import datetime
        project.updated_at = datetime.utcnow()
        await self.project_store.update_project(project)

        # Update cached project object
        self.user_projects[user_id] = project

        # Invalidate agent cache so next deliberation uses new prompts
        self.session_manager.invalidate_agent_cache(project.project_id)

        specialist_count = len(project.specialist_prompt_urls)
        await update.message.reply_text(
            f"✅ *Parliament updated*\n"
            f"Role `{role_label}` configured.\n"
            f"Parliament size: {specialist_count} specialist(s)\n\n"
            f"Use `/project_info` to see the full configuration.",
            parse_mode=ParseMode.MARKDOWN
        )

        logger.info("prompts_updated", user_id=user_id, project_id=project.project_id, role=role_label)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        # Get active session for this project
        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)

        if not session:
            await update.message.reply_text("No active session.")
            return

        msg = (
            f"📊 *Session Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ID: `{session.session_id}`\n"
            f"Status: {session.status}\n"
            f"Rounds: {len(session.rounds)}\n"
            f"Project: {session.project_name or project.name}\n\n"
            f"*Task:*\n{session.task}"
        )

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        sessions = await self.session_manager.session_store.get_user_sessions(
            user_id, project.project_id, limit=10
        )
        msg = self.formatter.format_session_history(sessions)

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
        if not session:
            await update.message.reply_text("No active session to cancel.")
            return

        await self.session_manager.cancel_session(session.session_id)

        await update.message.reply_text("❌ Session cancelled.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        text = update.message.text

        # Check whitelist
        if user_id not in settings.get_allowed_users():
            return

        project = self._get_project(user_id)

        # 1. Handle Awaiting Comment (Feedback for next round)
        if self.awaiting_comment.get(user_id):
            if project:
                session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                if session:
                    session.context = f"{session.context}\n\nUser Comment: {text}"
                    await self.session_manager.session_store.update_session(session)

                    # Also store as learning pattern
                    await self.session_manager.learn_from_text(project.project_id, f"Context (User Feedback): {text}")

                    self.awaiting_comment[user_id] = False
                    await update.message.reply_text("✅ Comment added for the next round! Click 'Continue' when ready.")
                    return
            self.awaiting_comment[user_id] = False

        # 2. Handle Awaiting Learn (Direct data entry)
        if self.awaiting_learn.get(user_id):
            if project:
                await self.session_manager.learn_from_text(project.project_id, text)
                self.awaiting_learn[user_id] = False
                await update.message.reply_text(
                    f"📝 Added to knowledge base for project: *{project.name}*",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            else:
                self.awaiting_learn[user_id] = False
                await update.message.reply_text("❌ No active project. Please use /project first.")
                return

        # 3. Standard Deliberation or knowledge capture
        if not project:
            if not text.startswith("/"):
                await update.message.reply_text("❌ No active project selected. Use /project.")
            return

        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)

        if session:
            if session.status == SessionStatus.DEAD_END:
                await self._handle_dead_end_feedback(update, session, text)
            else:
                await update.message.reply_text(
                    "⚠️ You have an active session. Use /cancel to cancel it first."
                )
            return

        # No active session — all text messages start deliberation
        if not text.startswith("/"):
            await self._start_deliberation(update, context, text, project)

    async def _start_deliberation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, project: Project):
        """Internal helper to start deliberation"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        specialist_count = len(project.specialist_prompt_urls)
        if specialist_count == 0:
            await update.message.reply_text(
                "⚠️ No specialists configured for this project.\n\n"
                "Add at least one specialist with:\n"
                "`/set_prompts specialist1 <url>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await update.message.reply_text(
            f"🏛️ *Starting Parliament deliberation...*\n"
            f"Parliament size: {specialist_count} specialist(s)",
            parse_mode=ParseMode.MARKDOWN
        )

        session = await self.session_manager.create_session(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            task=text,
            project_id=project.project_id,
            project_name=project.name
        )

        async def send_update(msg: str):
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN
            )

        try:
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )

            session = await self.session_manager.run_deliberation(
                session,
                progress_callback=send_update
            )

            await self._send_session_status_update(update, session)

        except Exception as e:
            logger.error("deliberation_error", error=str(e), session_id=session.session_id)
            await update.message.reply_text(
                f"❌ Error during deliberation:\n{str(e)}"
            )

    async def _handle_dead_end_feedback(self, update: Update, session, feedback: str):
        """Handle user feedback for dead-end session"""
        await update.message.reply_text("📝 Processing your feedback...")

        await self.session_manager.handle_user_feedback(
            session.session_id,
            feedback,
            restart=False
        )

        async def send_update(msg: str):
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

        try:
            session = await self.session_manager.continue_session(
                session.session_id,
                progress_callback=send_update
            )

            await self._send_session_status_update(update, session)

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
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await query.edit_message_text(
                            "Restarting deliberation...\n"
                            "Please provide new direction or clarification."
                        )

        elif data.startswith("implement:"):
            session_id = data.split(":", 1)[1]
            await self._handle_implement(query, context, user_id, session_id)

        elif data.startswith("session:"):
            action = data.split(":")[1]

            if action == "cancel":
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await self.session_manager.cancel_session(session.session_id)
                        await query.edit_message_text("❌ Session cancelled.")

            elif action == "continue":
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await self._handle_continuation(query, session)

            elif action == "comment":
                self.awaiting_comment[user_id] = True
                await query.message.reply_text(
                    "💬 Please send your comment/feedback. It will be added to the next round's context."
                )

    async def cmd_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /code command for direct code implementation."""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("⚠️ No active project. Use /project <name> first.")
            return

        if not self.code_workflow:
            await update.message.reply_text("⚠️ Code workflow is not configured.")
            return

        if not settings.claude_code_enabled:
            await update.message.reply_text("⚠️ Claude Code integration is disabled.")
            return

        text = update.message.text
        task_desc = text.replace('/code', '').strip()

        if not task_desc:
            await update.message.reply_text(
                "📝 Usage: /code <description>\n\n"
                "Example: /code Add Redis caching to vessel.py"
            )
            return

        project_path = Path(settings.projects_root) / project.name
        if not project_path.exists():
            await update.message.reply_text(
                f"⚠️ Project directory not found: {project_path}"
            )
            return

        await update.message.reply_text(
            f"🚀 *Implementing:* {self.formatter.escape_markdown(task_desc)}\n\n"
            "Claude Code is working on it...",
            parse_mode=ParseMode.MARKDOWN,
        )

        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        try:
            result = await self.code_workflow.implement_direct(task_desc, project_path)
            msg = self.formatter.format_implementation_result(result)
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error("code_command_error", error=str(e))
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command for code analysis."""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("⚠️ No active project. Use /project <name> first.")
            return

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
            "⏳ Analyzing..."
        )

        await update.message.reply_text(
            "✅ Analysis complete!\n\n"
            "Full analysis integration coming soon."
        )

    async def cmd_validate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /validate command for code validation."""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("⚠️ No active project. Use /project <name> first.")
            return

        await update.message.reply_text(
            "🔍 Running validation...\n\n"
            "⏳ Validating..."
        )

        await update.message.reply_text(
            "✅ *Validation Results*\n\n"
            "Validation integration coming soon.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /export command to export full conversation as JSON."""
        user_id = update.effective_user.id
        project = self._get_project(user_id)

        if not project:
            await update.message.reply_text("❌ No active project. Please use /project first.")
            return

        session = None
        session_num = None

        text = update.message.text
        parts = text.split()

        if len(parts) > 1:
            try:
                session_num = int(parts[1])

                sessions = await self.session_manager.session_store.get_user_sessions(
                    user_id, project.project_id, limit=20
                )

                if not sessions:
                    await update.message.reply_text("No past sessions found.")
                    return

                if session_num < 1 or session_num > len(sessions):
                    await update.message.reply_text(
                        f"❌ Session number must be between 1 and {len(sessions)}"
                    )
                    return

                session = sessions[session_num - 1]

            except ValueError:
                await update.message.reply_text("❌ valid session number required (e.g. /export 1)")
                return
        else:
            session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
            if not session:
                sessions = await self.session_manager.session_store.get_user_sessions(
                    user_id, project.project_id, limit=1
                )
                if sessions:
                    session = sessions[0]
                    session_num = 1
                else:
                    await update.message.reply_text(
                        "No specific session request and no active/recent session found.\n"
                        "Use /history to see past sessions."
                    )
                    return

        await update.message.reply_text(f"📦 Exporting session {session.session_id}...")

        try:
            import json
            import os

            filename = f"session_{session.session_id}.json"
            json_str = session.model_dump_json(indent=2)

            with open(filename, 'w') as f:
                f.write(json_str)

            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=f"📊 Session Export: {session.session_id}\nStatus: {session.status.value}"
                )

            os.remove(filename)

            logger.info("session_exported", session_id=session.session_id, user_id=user_id)

        except Exception as e:
            logger.error("export_failed", error=str(e), session_id=session.session_id if session else "unknown")
            await update.message.reply_text(f"❌ Export failed: {str(e)}")

    async def _handle_implement(self, query, context, user_id: int, session_id: str):
        """Handle implementation request after consensus"""
        if not self.code_workflow or not settings.claude_code_enabled:
            await query.edit_message_text("⚠️ Claude Code integration is not available.")
            return

        project = self._get_project(user_id)
        if not project:
            await query.edit_message_text("⚠️ No active project selected.")
            return

        project_path = Path(settings.projects_root) / project.name
        if not project_path.exists():
            await query.edit_message_text(f"⚠️ Project directory not found: {project_path}")
            return

        session = await self.session_manager.session_store.get_session(session_id)
        if not session:
            await query.edit_message_text("⚠️ Session not found.")
            return

        await query.edit_message_text(
            "🚀 *Implementing consensus...*\n\n"
            "Claude Code is working on it...",
            parse_mode=ParseMode.MARKDOWN,
        )
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id, action=ChatAction.TYPING
        )

        try:
            result = await self.code_workflow.implement_from_consensus(session, project_path)
            msg = self.formatter.format_implementation_result(result)
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error("implement_error", error=str(e), session_id=session_id)
            await query.message.reply_text(f"❌ Implementation error: {str(e)}")

    async def _handle_continuation(self, query, session):
        """Handle session continuation after pause"""
        # Remove buttons from the round summary so it stays readable in chat
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        async def send_update(msg: str):
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

        try:
            session = await self.session_manager.run_deliberation(
                session,
                progress_callback=send_update
            )

            await self._send_session_status_update(query, session)

        except Exception as e:
            logger.error("continue_error", error=str(e))
            await query.message.reply_text(f"❌ Error: {str(e)}")

    async def _send_session_status_update(self, update_or_query, session):
        """Send appropriate message based on current session status"""
        if hasattr(update_or_query, 'message') and update_or_query.message:
            target = update_or_query.message
        else:
            target = update_or_query

        if session.status == SessionStatus.CONSENSUS:
            result_msg = self.formatter.format_consensus_decision(session)
            reply_markup = None
            if self.code_workflow and settings.claude_code_enabled:
                project = self._get_project(session.telegram_user_id)
                if project:
                    reply_markup = self.keyboards.consensus_keyboard(session.session_id)
            await target.reply_text(
                result_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
        elif session.status == SessionStatus.DEAD_END:
            dead_end_msg = self.formatter.format_dead_end(session)
            await target.reply_text(
                dead_end_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.keyboards.dead_end_keyboard()
            )
        elif session.status == SessionStatus.AWAITING_CONTINUATION:
            round_msg = self.formatter.format_round_update(session.rounds[-1])
            await target.reply_text(
                round_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.keyboards.session_continue_keyboard()
            )
