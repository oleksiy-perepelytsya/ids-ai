"""Transport-agnostic command handler.

All business logic for IDS commands lives here.  The handler receives
``Message`` objects and returns ``Reply`` objects — it never touches
Telegram, HTTP, or any other transport directly.

Each interface adapter is responsible for:
1. Parsing its native input into a ``Message``
2. Passing it to the appropriate ``cmd_*`` / ``handle_*`` method
3. Delivering the returned ``Reply`` via ``InterfaceAdapter.send``
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import aiohttp

from ids.config import settings
from ids.interfaces.base import (
    Attachment,
    Button,
    InterfaceAdapter,
    Message,
    MessageFormat,
    Reply,
)
from ids.models import Project, SessionStatus, PromptLibraryEntry
from ids.orchestrator import SessionManager
from ids.orchestrator.code_workflow import CodeWorkflow
from ids.storage import MongoProjectStore
from ids.utils import get_logger

logger = get_logger(__name__)


_MD2_ESC = re.compile(r'([_*\[\]()~`>#+\-=|{}.!\\])')


def _esc(text: str) -> str:
    """Escape all MarkdownV2 special chars in user-supplied plain text."""
    if not text:
        return ""
    return _MD2_ESC.sub(r'\\\1', text)


class CommandHandler:
    """Core command handler — shared across every interface."""

    def __init__(
        self,
        session_manager: SessionManager,
        project_store: MongoProjectStore,
        adapter: InterfaceAdapter,
        code_workflow: Optional[CodeWorkflow] = None,
        daily_update_service=None,
    ):
        self.session_manager = session_manager
        self.project_store = project_store
        self.adapter = adapter
        self.code_workflow = code_workflow
        self.daily_update_service = daily_update_service

        # Per-user state
        self.user_projects: dict[int, Project] = {}
        self.awaiting_comment: dict[int, bool] = {}
        self.awaiting_learn: dict[int, bool] = {}

        logger.info("command_handler_initialized")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_project(self, user_id: int) -> Optional[Project]:
        return self.user_projects.get(user_id)

    async def _reply(self, msg: Message, reply: Reply) -> None:
        """Convenience: send *reply* to the chat the *msg* came from."""
        await self.adapter.send(msg.user.chat_id, reply)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def cmd_start(self, msg: Message) -> None:
        user_id = msg.user.user_id
        if not self.adapter.is_authorized(msg.user):
            await self._reply(msg, Reply(
                text="⛔ Sorry, you're not authorized to use this bot.",
                format=MessageFormat.PLAIN,
            ))
            logger.warning("unauthorized_access_attempt", user_id=user_id)
            return

        await self._reply(msg, Reply(text=(
            "👋 *Welcome to IDS!*\n"
            "🏛️ Multi\\-agent deliberation platform\n\n"
            "1\\. Register a project: `/register_project <name>`\n"
            "2\\. Configure specialists: `/set_prompts specialist1 <url>`\n"
            "3\\. Switch to it: `/project <name>`\n"
            "4\\. Send any text to start a parliament deliberation\n\n"
            "Use /help to see all available commands\\."
        )))
        logger.info("user_started", user_id=user_id)

    async def cmd_help(self, msg: Message) -> None:
        if not msg.args:
            # No question — show commands overview with invitation to ask
            await self._reply(msg, Reply(text=(
                "*IDS Commands*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "*Project Management:*\n"
                "/register\\_project <name> \\[desc\\] — Register a new project\n"
                "/list\\_projects — List all your projects\n"
                "/project \\[name\\] — Show or switch active project\n"
                "/project\\_info — Show parliament config and session stats\n"
                "/set\\_prompts <role> <url> — Configure specialist/generalist/sourcer prompts\n"
                "/set\\_model generalist <claude|gemini> — Switch generalist LLM model\n"
                "/set\\_rounds <n> — Set max deliberation rounds before dead\\-end\n"
                "/delete\\_project <name> — Remove project and all its data\n\n"
                "*Deliberation:*\n"
                "💬 Send any text — Start a parliament deliberation\n"
                "/status — Show active session info\n"
                "/history — View past sessions for current project\n"
                "/export \\[n\\] — Export session as JSON file\n"
                "/cancel — Cancel the active session\n\n"
                "*Knowledge Base:*\n"
                "/learn \\[text\\] — Add text to knowledge base\n"
                "/embed <filepath> — Embed a local file into knowledge base\n"
                "/sourcer <model> <query> — Query knowledge base \\(model: claude/gemini/llama\\)\n"
                "📎 Send any file — Embed file into knowledge base \\(txt, md, py, pdf, \\.\\.\\.\\)\n\n"
                "*Code \\(Claude Code integration\\):*\n"
                "/code <task> — Implement a task directly with Claude Code\n"
                "/analyze <filepath> — Analyze a file\n"
                "/validate — Validate recent changes\n\n"
                "*Other:*\n"
                "/start — Welcome message\n"
                "/help — Show this help\n"
                "/daily\\_update — Collect planetary fingerprint\n\n"
                "💡 *Ask me anything:* `/help <your question>`\n"
                "Models: `/help claude|gemini|llama <question>` \\(default: gemini\\)\n"
                "Example: `/help how do I add a specialist?`"
            )))
            return

        # Parse optional model prefix (same pattern as /sourcer)
        VALID_MODELS = ["claude", "gemini", "llama", "local"]
        remaining = list(msg.args)
        model = "gemini"  # default — budget-friendly
        if remaining[0].lower() in VALID_MODELS:
            model = remaining.pop(0).lower()

        if not remaining:
            await self._reply(msg, Reply(
                text="❓ Please provide a question after the model name\\.\n"
                     "Example: `/help gemini how do I configure specialists?`",
            ))
            return

        question = " ".join(remaining)
        user_id = msg.user.user_id

        is_local = model in ("llama", "local")
        label = "Llama (local)" if is_local else model.capitalize()
        await self._reply(msg, Reply(text=f"🤖 *Thinking* \\({_esc(label)}\\)\\.\\.\\." ))

        keep_typing = None
        try:
            if is_local:
                keep_typing = self.adapter.make_keep_typing_task(msg.user.chat_id)
            else:
                await self.adapter.show_typing(msg.user.chat_id)

            # Load hostess prompt from persona file
            from ids.services.prompt_loader import load_fallback_prompt
            system_prompt = load_fallback_prompt("hostess.md")

            # Gather rich context via dedicated service
            from ids.services.hostess_context import build_hostess_context
            user_context = await build_hostess_context(
                user_id=user_id,
                project=self._get_project(user_id),
                question=question,
                session_store=self.session_manager.session_store,
                project_store=self.project_store,
                search=self.session_manager.search,
            )

            response = await self.session_manager.llm_client.call_model(
                model=model,
                prompt=(
                    f"User question: {question}\n\n"
                    f"Current user context:\n{user_context}"
                ),
                system_prompt=system_prompt,
                max_tokens=2000,
            )

            CHUNK = 4000
            for i in range(0, len(response), CHUNK):
                await self._reply(msg, Reply(
                    text=response[i:i + CHUNK],
                    format=MessageFormat.PLAIN,
                ))
        except Exception as e:
            logger.error("help_hostess_error", error=str(e))
            await self._reply(msg, Reply(
                text=f"❌ Sorry, I couldn't process your question: {e}",
                format=MessageFormat.PLAIN,
            ))
        finally:
            if keep_typing is not None:
                keep_typing.cancel()

    async def cmd_register_project(self, msg: Message) -> None:
        user_id = msg.user.user_id
        if not msg.args:
            await self._reply(msg, Reply(text=(
                "Usage: /register\\_project <name> <description>\n\n"
                "Example: /register\\_project maritime Maritime business decisions"
            )))
            return

        project_name = msg.args[0]
        description = " ".join(msg.args[1:]) if len(msg.args) > 1 else None

        existing = await self.project_store.get_project_by_name(project_name, user_id)
        if existing:
            await self._reply(msg, Reply(
                text=f"⚠️ Project '{project_name}' already exists.",
                format=MessageFormat.PLAIN,
            ))
            return

        project = Project(
            project_id=f"proj_{uuid.uuid4().hex[:8]}",
            name=project_name,
            description=description,
            user_id=user_id,
        )
        await self.project_store.create_project(project)
        self.user_projects[user_id] = project

        await self._reply(msg, Reply(text=(
            f"✅ Project *{project_name}* registered and selected\\!\n\n"
            f"Configure parliament with:\n"
            f"`/set_prompts specialist1 <url>`\n"
            f"`/set_prompts specialist2 <url>`\n"
            f"`/set_prompts generalist <url>` \\(optional\\)\n\n"
            f"Ready\\! Use `/learn`, send files, or configure specialists\\."
        )))
        logger.info("project_registered", user_id=user_id, project=project_name)

    async def cmd_list_projects(self, msg: Message) -> None:
        user_id = msg.user.user_id
        projects = await self.project_store.get_user_projects(user_id)
        if not projects:
            await self._reply(msg, Reply(
                text=f"You have no registered projects (queried user_id={user_id}).\n\nUse /register_project to create one.",
                format=MessageFormat.PLAIN,
            ))
            return

        parts = ["📂 *Your Projects:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]
        for p in projects:
            sc = len(set(p.specialist_prompt_urls) | set(p.specialist_prompts))
            parts.append(f"• *{_esc(p.name)}*")
            if p.description:
                parts.append(f" — {_esc(p.description)}")
            parts.append(f"\n  Specialists: {sc} configured\n\n")
        parts.append("Use /project <name> to switch\\.")
        await self._reply(msg, Reply(text="".join(parts)))

    async def cmd_project(self, msg: Message) -> None:
        user_id = msg.user.user_id
        if not msg.args:
            project = self._get_project(user_id)
            if project:
                await self._reply(msg, Reply(text=(
                    f"📂 Current project: *{_esc(project.name)}*\n\n"
                    f"Use /project <name> to switch\\."
                )))
            else:
                await self._reply(msg, Reply(text=(
                    "📂 No project selected\\.\n\nUse /project <name> to switch\\."
                )))
            return

        project_name = msg.args[0]
        project = await self.project_store.get_project_by_name(project_name, user_id)
        if not project:
            await self._reply(msg, Reply(text=(
                f"⚠️ Project '{project_name}' not found.\n"
                f"Use /list\\_projects to see available projects."
            )))
            return

        self.user_projects[user_id] = project
        sc = len(set(project.specialist_prompt_urls) | set(project.specialist_prompts))
        await self._reply(msg, Reply(text=(
            f"📂 Switched to project: *{_esc(project.name)}*\n"
            f"Parliament: {sc} specialist\\(s\\) configured\n\n"
            f"Ready for your questions\\!"
        )))
        logger.info("project_switched", user_id=user_id, project=project_name, project_id=project.project_id)

    async def cmd_project_info(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        sessions = await self.session_manager.session_store.get_user_sessions(user_id, project.project_id, limit=100)
        session_count = len(sessions)
        last_date = sessions[0].created_at.strftime("%Y-%m-%d") if sessions else ""

        agents = self.session_manager._agent_cache.get(project.project_id)

        # Build info text
        all_keys = sorted(
            set(project.specialist_prompt_urls.keys()) | set(project.specialist_prompts.keys()),
            key=int,
        )
        sc = len(all_keys)
        parts = [
            f"📂 *Project: {_esc(project.name)}* (`{project.project_id}`)\n",
            "━━━━━━━━━━━━━━━━━━━━\n",
        ]
        if project.description:
            parts.append(f"Description: {_esc(project.description)}\n")
        parts.append(f"\n*Parliament ({sc} specialists):*\n")
        if sc == 0:
            parts.append("  No specialists configured yet\\.\n")
        else:
            for key in all_keys:
                if key in project.specialist_prompts:
                    rn = project.specialist_role_names.get(key, "library prompt")
                    parts.append(f"• specialist\\_{key}: `{_esc(rn)}` \\(generated\\)\n")
                else:
                    url = project.specialist_prompt_urls[key]
                    parts.append(f"• specialist\\_{key}: `{_esc(url)}`\n")

        parts.append("\n*Roles:*\n")
        gm = _esc(project.generalist_model) if project.generalist_model else "claude (default)"
        if project.generalist_prompt_url:
            parts.append(f"• Generalist: `{project.generalist_prompt_url}` \\[model: {gm}, max {project.generalist_max_tokens} tokens\\]\n")
        else:
            parts.append(f"• Generalist: using default \\[model: {gm}, max {project.generalist_max_tokens} tokens\\]\n")
        if project.sourcer_prompt_url:
            parts.append(f"• Sourcer: `{project.sourcer_prompt_url}` \\[max {project.sourcer_max_tokens} tokens\\]\n")
        else:
            parts.append(f"• Sourcer: using default \\[max {project.sourcer_max_tokens} tokens\\]\n")
        parts.append(f"• Specialists: max {project.specialist_max_tokens} tokens each\n")

        parts.append("\n*Deliberation Settings:*\n")
        mr = project.max_rounds if project.max_rounds else settings.max_rounds
        rs = "project" if project.max_rounds else "global default"
        parts.append(f"• Max rounds: `{mr}` \\({rs}\\)\n")

        if session_count > 0:
            parts.append(f"\n*Sessions:* {session_count} total")
            if last_date:
                parts.append(f", last: {last_date}")
            parts.append("\n")

        # Append loaded role names
        if agents:
            role_lines = []
            for key in all_keys:
                role_id = f"specialist_{key}"
                agent = agents.get(role_id)
                if agent:
                    role_lines.append(f"• specialist\\_{key} → *{_esc(agent.role_name)}*")
            if role_lines:
                parts.append("\n*Loaded Role Names:*\n" + "\n".join(role_lines) + "\n")

        parts.append(
            "\n*Configure parliament with:*\n"
            "`/set_prompts specialist1 <url>`\n"
            "`/set_prompts specialist2 <url>`\n"
            "`/set_prompts generalist <url>` \\(optional\\)\n"
            "`/set_model generalist <claude|gemini>`\n"
            "`/set_rounds <n>`\n"
        )
        await self._reply(msg, Reply(text="".join(parts)))

    async def cmd_set_prompts(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if len(msg.args) < 2:
            await self._reply(msg, Reply(text=(
                "*Configure Parliament Prompts*\n\n"
                "Usage: `/set_prompts <role> <url>`\n\n"
                "Roles:\n"
                "• `generalist` — main synthesizer \\(Claude\\)\n"
                "• `sourcer` — knowledge retrieval \\(Gemini\\)\n"
                "• `specialist1`, `specialist2`, \\.\\.\\. — domain experts \\(Gemini\\)\n\n"
                "Example:\n"
                "`/set_prompts specialist1 https://raw.githubusercontent.com/.../maritime.md`"
            )))
            return

        role_arg = msg.args[0].lower()
        url = msg.args[1]

        is_url = url.startswith("http://") or url.startswith("https://")
        if is_url:
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as http_client:
                    async with http_client.head(url, allow_redirects=True) as resp:
                        if resp.status >= 400:
                            async with http_client.get(url, allow_redirects=True) as resp2:
                                if resp2.status >= 400:
                                    await self._reply(msg, Reply(
                                        text=f"❌ URL returned HTTP {resp2.status}. Please check the URL.",
                                        format=MessageFormat.PLAIN,
                                    ))
                                    return
            except Exception as e:
                await self._reply(msg, Reply(text=f"❌ Could not reach URL: {e}", format=MessageFormat.PLAIN))
                return

        project = await self.project_store.get_project(project.project_id)

        if role_arg == "generalist":
            project.generalist_prompt_url = url
            role_label = "generalist"
        elif role_arg == "sourcer":
            project.sourcer_prompt_url = url
            role_label = "sourcer"
        elif role_arg == "genprompt":
            project.genprompt_prompt_url = url
            role_label = "genprompt"
        elif re.match(r'^specialist(\d+)$', role_arg):
            key = re.match(r'^specialist(\d+)$', role_arg).group(1)
            if url.lower() == "rm":
                removed = (
                    project.specialist_prompt_urls.pop(key, None) or
                    project.specialist_prompts.pop(key, None)
                )
                project.specialist_role_names.pop(key, None)
                if not removed:
                    await self._reply(msg, Reply(text=f"⚠️ specialist{key} was not configured.", format=MessageFormat.PLAIN))
                    return
                role_label = f"specialist_{key} (removed)"
            elif is_url:
                project.specialist_prompt_urls[key] = url
                project.specialist_prompts.pop(key, None)
                project.specialist_role_names.pop(key, None)
                role_label = f"specialist_{key} (url)"
            else:
                entry = await self.session_manager.session_store.get_prompt_library_entry(project.project_id, url)
                if not entry:
                    await self._reply(msg, Reply(text=(
                        f"❌ No generated prompt found for role `{url}`.\n"
                        f"Run `/genprompt <model> {url}` first to generate one."
                    )))
                    return
                project.specialist_prompts[key] = entry.prompt
                project.specialist_role_names[key] = url
                project.specialist_prompt_urls.pop(key, None)
                role_label = f"specialist_{key} ({url})"
        else:
            await self._reply(msg, Reply(
                text="❌ Unknown role. Use: `generalist`, `sourcer`, `genprompt`, `specialist1`, `specialist2`, ...",
                format=MessageFormat.PLAIN,
            ))
            return

        project.updated_at = datetime.utcnow()
        await self.project_store.update_project(project)
        self.user_projects[user_id] = project
        self.session_manager.invalidate_agent_cache(project.project_id)

        sc = len(set(project.specialist_prompt_urls) | set(project.specialist_prompts))
        await self._reply(msg, Reply(text=(
            f"✅ *Parliament updated*\n"
            f"Role `{_esc(role_label)}` configured\\.\n"
            f"Parliament size: {sc} specialist\\(s\\)\n\n"
            f"Use `/project_info` to see the full configuration\\."
        )))
        logger.info("prompts_updated", user_id=user_id, project_id=project.project_id, role=role_label)

    async def cmd_genprompt(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if len(msg.args) < 2:
            await self._reply(msg, Reply(text=(
                "🧠 *Prompt Generator*\n"
                "Usage: `/genprompt <model> <role_name>`\n\n"
                "Example: `/genprompt claude marine_biologist`\n"
                "Example: `/genprompt gemini sonochemistry_specialist`\n\n"
                "Generated prompts are stored and can be assigned with:\n"
                "`/set_prompts specialist1 marine_biologist`"
            )))
            return

        VALID_MODELS = ["claude", "gemini", "llama", "local"]
        gen_model = msg.args[0].lower()
        if gen_model not in VALID_MODELS:
            await self._reply(msg, Reply(text=f"❌ Invalid model. Use: {', '.join(VALID_MODELS)}", format=MessageFormat.PLAIN))
            return

        role_name = msg.args[1].lower().replace(" ", "_")
        extra_instruction = " ".join(msg.args[2:]) if len(msg.args) > 2 else ""

        await self._reply(msg, Reply(text=(
            f"🧠 Generating specialist prompt for *{_esc(role_name)}* using *{_esc(gen_model)}*\\.\\.\\."
        )))

        try:
            genprompt_system = (
                "You are an expert AI system prompt engineer. "
                "Generate a detailed, high-quality system prompt for a specialist agent "
                "that will participate in a multi-agent deliberation parliament. "
                "The prompt must include '# Role: <role name>' on the first line, "
                "followed by deep domain expertise, analytical framework, and instructions "
                "to provide CROSS scores (Confidence/Risk/Outcome 0-100) in responses. "
                "Return only the system prompt text, no commentary."
            )
            if project.genprompt_prompt_url:
                from ids.services.prompt_loader import fetch_or_fallback
                custom = await fetch_or_fallback(project.genprompt_prompt_url, None)
                if custom:
                    genprompt_system = custom

            user_msg = (
                f"Generate a specialist system prompt for: {role_name}\n"
                f"Project context: {project.name}"
                + (f" — {project.description}" if project.description else "")
                + (f"\n\nAdditional instructions: {extra_instruction}" if extra_instruction else "")
            )

            generated = await self.session_manager.llm_client.call_model(
                model=gen_model,
                prompt=user_msg,
                system_prompt=genprompt_system,
                max_tokens=3000,
            )

            entry = PromptLibraryEntry(
                entry_id=f"plb_{uuid.uuid4().hex[:12]}",
                project_id=project.project_id,
                role_name=role_name,
                prompt=generated,
                generator_model=gen_model,
            )
            await self.session_manager.session_store.save_prompt_library_entry(entry)

            await self._reply(msg, Reply(text=(
                f"✅ *Prompt generated and stored* for `{_esc(role_name)}`\n\n"
                f"Assign it with: `/set_prompts specialist1 {_esc(role_name)}`"
            )))
            CHUNK = 4000
            for i in range(0, len(generated), CHUNK):
                await self._reply(msg, Reply(text=generated[i:i + CHUNK], format=MessageFormat.PLAIN))

            logger.info("genprompt_created", role_name=role_name, project_id=project.project_id, model=gen_model)
        except Exception as e:
            logger.error("genprompt_failed", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Generation failed: {e}", format=MessageFormat.PLAIN))

    async def cmd_list_prompts(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        entries = await self.session_manager.session_store.list_prompt_library(project.project_id)
        if not entries:
            await self._reply(msg, Reply(
                text="📚 No generated prompts yet.\nUse `/genprompt <model> <role_name>` to generate one.",
                format=MessageFormat.PLAIN,
            ))
            return

        assigned = {v: k for k, v in project.specialist_role_names.items()}
        lines = [f"📚 Prompt Library — {project.name}\n"]
        for e in entries:
            slot = assigned.get(e.role_name)
            slot_tag = f" → specialist{slot}" if slot else " (unassigned)"
            preview = e.prompt[:100].replace("\n", " ")
            lines.append(f"• {e.role_name}{slot_tag} [{e.generator_model}]\n  {preview}…")
        lines.append(f"\nTotal: {len(entries)} prompt(s)")
        await self._reply(msg, Reply(text="\n".join(lines), format=MessageFormat.PLAIN))

    async def cmd_set_model(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if len(msg.args) < 2:
            current_gen = project.generalist_model or f"claude (default: `{_esc(settings.claude_model)}`)"
            current_emb = project.embedding_model or "minilm"
            await self._reply(msg, Reply(text=(
                "*Model Configuration*\n\n"
                f"• Generalist LLM: `{_esc(str(current_gen))}`\n"
                f"• Embedding model: `{_esc(current_emb)}`\n\n"
                f"• Sourcer max tokens: `{project.sourcer_max_tokens}`\n"
                f"• Generalist max tokens: `{project.generalist_max_tokens}`\n"
                f"• Specialist max tokens: `{project.specialist_max_tokens}`\n\n"
                "Usage: `/set_model <role> <value>`\n\n"
                "*Generalist LLM:*\n"
                "`/set_model generalist claude`\n"
                "`/set_model generalist gemini`\n\n"
                "*Embedding model \\(knowledge base\\):*\n"
                "`/set_model embedding default` — all\\-MiniLM, no API key\n"
                "`/set_model embedding ada-002` — OpenAI ada\\-002, requires OPENAI\\_API\\_KEY\n\n"
                "*Response token limits:*\n"
                "`/set_model sourcer_tokens 8000`\n"
                "`/set_model generalist_tokens 4000`\n"
                "`/set_model specialist_tokens 2000`"
            )))
            return

        role_arg = msg.args[0].lower()
        model_arg = msg.args[1].lower()

        # Embedding model
        if role_arg == "embedding":
            from ids.search.embeddings import EMBEDDING_REGISTRY, _ALIASES
            valid_keys = set(EMBEDDING_REGISTRY) | set(_ALIASES)
            if model_arg not in valid_keys:
                keys_str = ", ".join(f"`{k}`" for k in sorted(EMBEDDING_REGISTRY))
                await self._reply(msg, Reply(text=(
                    f"❌ Unknown embedding model\\. Available: {_esc(keys_str)}"
                )))
                return
            if model_arg == "ada-002" and not settings.openai_api_key:
                await self._reply(msg, Reply(text="❌ `OPENAI_API_KEY` is not set in your `.env`\\. Add it first\\."))
                return
            project = await self.project_store.get_project(project.project_id)
            project.embedding_model = model_arg
            project.updated_at = datetime.utcnow()
            await self.project_store.update_project(project)
            self.user_projects[user_id] = project
            await self._reply(msg, Reply(text=(
                f"✅ *Embedding model updated*\n\n"
                f"• Model: `{_esc(model_arg)}`\n"
                f"• Project: *{_esc(project.name)}*\n\n"
                f"⚠️ Existing collection data uses the old embedding space\\.\n"
                f"Run `/delete_project` and re\\-import if you want a clean collection\\."
            )))
            logger.info("embedding_model_updated", user_id=user_id, project_id=project.project_id, model=model_arg)
            return

        # Token limits
        TOKEN_FIELDS = {
            "sourcer_tokens": "sourcer_max_tokens",
            "generalist_tokens": "generalist_max_tokens",
            "specialist_tokens": "specialist_max_tokens",
        }
        if role_arg in TOKEN_FIELDS:
            try:
                new_limit = int(msg.args[1])
                if new_limit < 100 or new_limit > 32000:
                    raise ValueError
            except ValueError:
                await self._reply(msg, Reply(text="❌ Token limit must be an integer between 100 and 32000.", format=MessageFormat.PLAIN))
                return
            project = await self.project_store.get_project(project.project_id)
            setattr(project, TOKEN_FIELDS[role_arg], new_limit)
            project.updated_at = datetime.utcnow()
            await self.project_store.update_project(project)
            self.user_projects[user_id] = project
            self.session_manager.invalidate_agent_cache(project.project_id)
            await self._reply(msg, Reply(text=(
                f"✅ *Token limit updated*\n\n"
                f"• Role: `{_esc(role_arg)}`\n"
                f"• Limit: `{new_limit}` tokens\n"
                f"• Project: *{_esc(project.name)}*"
            )))
            logger.info("token_limit_updated", user_id=user_id, project_id=project.project_id, role=role_arg, limit=new_limit)
            return

        # Generalist LLM model
        if role_arg != "generalist":
            await self._reply(msg, Reply(text=(
                "❌ Unknown role. Use:\n"
                "• `generalist claude|gemini` — switch LLM\n"
                "• `embedding ada-002|default` — switch embedding model\n"
                "• `sourcer_tokens|generalist_tokens|specialist_tokens <N>` — set token limits"
            ), format=MessageFormat.PLAIN))
            return

        MODEL_ALIASES = {"claude": settings.claude_model, "gemini": settings.gemini_model}
        if model_arg not in MODEL_ALIASES:
            await self._reply(msg, Reply(text=f"❌ Unknown model `{_esc(model_arg)}`. Use `claude` or `gemini`.", format=MessageFormat.PLAIN))
            return

        model_id = MODEL_ALIASES[model_arg]
        project = await self.project_store.get_project(project.project_id)
        project.generalist_model = model_id
        project.updated_at = datetime.utcnow()
        await self.project_store.update_project(project)
        self.user_projects[user_id] = project
        self.session_manager.invalidate_agent_cache(project.project_id)

        await self._reply(msg, Reply(text=(
            f"✅ *Generalist model updated*\n\n"
            f"• Role: `generalist`\n"
            f"• Model: `{_esc(model_id)}`\n"
            f"• Project: *{_esc(project.name)}*"
        )))
        logger.info("generalist_model_updated", user_id=user_id, project_id=project.project_id, model=model_id)

    async def cmd_set_rounds(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if not msg.args:
            current = project.max_rounds or settings.max_rounds
            source = "project" if project.max_rounds else "global default"
            await self._reply(msg, Reply(text=(
                f"*Deliberation Rounds*\n\n"
                f"Current: `{current}` ({source})\n\n"
                f"Usage: `/set_rounds <n>` \\(1–10\\)"
            )))
            return

        try:
            n = int(msg.args[0])
        except ValueError:
            await self._reply(msg, Reply(text="❌ Please provide a number, e.g. `/set_rounds 5`", format=MessageFormat.PLAIN))
            return

        if not (1 <= n <= 10):
            await self._reply(msg, Reply(text="❌ Rounds must be between 1 and 10.", format=MessageFormat.PLAIN))
            return

        project = await self.project_store.get_project(project.project_id)
        project.max_rounds = n
        project.updated_at = datetime.utcnow()
        await self.project_store.update_project(project)
        self.user_projects[user_id] = project

        await self._reply(msg, Reply(text=(
            f"✅ *Max rounds updated*\n\n"
            f"• Rounds: `{n}`\n"
            f"• Project: *{_esc(project.name)}*"
        )))
        logger.info("max_rounds_updated", user_id=user_id, project_id=project.project_id, max_rounds=n)

    async def cmd_delete_project(self, msg: Message) -> None:
        user_id = msg.user.user_id
        if not msg.args:
            await self._reply(msg, Reply(text=(
                "Usage: `/delete_project <name>`\n\n"
                "This removes the project, all its sessions, and all vector data."
            )))
            return

        project_name = msg.args[0]
        project = await self.project_store.get_project_by_name(project_name, user_id)
        if not project:
            await self._reply(msg, Reply(text=f"⚠️ Project '{project_name}' not found.", format=MessageFormat.PLAIN))
            return

        sc = len(set(project.specialist_prompt_urls) | set(project.specialist_prompts))
        await self._reply(msg, Reply(
            text=(
                f"⚠️ *Delete project '{project_name}'?*\n\n"
                f"This will permanently remove:\n"
                f"• The project and its {sc} specialist prompt(s)\n"
                f"• All deliberation sessions\n"
                f"• All learning data \\(vector store\\)\n\n"
                f"*This cannot be undone.*"
            ),
            buttons=[
                [Button("🗑️ Yes, delete everything", f"delete_project:confirm:{project.project_id}")],
                [Button("❌ Cancel", f"delete_project:cancel:{project.project_id}")],
            ],
        ))

    async def cmd_status(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
        if not session:
            await self._reply(msg, Reply(text="No active session.", format=MessageFormat.PLAIN))
            return

        await self._reply(msg, Reply(text=(
            f"📊 *Session Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ID: `{session.session_id}`\n"
            f"Status: {session.status}\n"
            f"Rounds: {len(session.rounds)}\n"
            f"Project: {_esc(session.project_name or project.name)}\n\n"
            f"*Task:*\n{_esc(session.task)}"
        )))

    async def cmd_history(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        sessions = await self.session_manager.session_store.get_user_sessions(user_id, project.project_id, limit=10)
        if not sessions:
            await self._reply(msg, Reply(text="No previous sessions found for this project.", format=MessageFormat.PLAIN))
            return

        parts = ["📜 *Recent Sessions:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]
        for s in sessions[:5]:
            emoji = {"consensus": "✅", "dead_end": "⚠️", "cancelled": "❌", "deliberating": "⏳"}.get(s.status, "❓")
            task_preview = _esc(s.task[:50])
            parts.append(
                f"{emoji} {task_preview}\\.\\.\\.\n"
                f"   ID: `{s.session_id}`\n"
                f"   Status: {s.status}\n"
                f"   Rounds: {len(s.rounds)}\n\n"
            )
        await self._reply(msg, Reply(text="".join(parts)))

    async def cmd_cancel(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
        if not session:
            await self._reply(msg, Reply(text="No active session to cancel.", format=MessageFormat.PLAIN))
            return

        await self.session_manager.cancel_session(session.session_id)
        await self._reply(msg, Reply(text="❌ Session cancelled.", format=MessageFormat.PLAIN))

    async def cmd_learn(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if msg.args:
            text = " ".join(msg.args)
            await self.session_manager.learn_from_text(project.project_id, text, embedding_model=project.embedding_model)
            await self._reply(msg, Reply(text=f"📝 Added to knowledge base for project: *{_esc(project.name)}*"))
        else:
            self.awaiting_learn[user_id] = True
            await self._reply(msg, Reply(text="📝 Please send the text you want me to learn and store in the knowledge base.", format=MessageFormat.PLAIN))

    async def cmd_embed(self, msg: Message) -> None:
        """Embed a local file into the project knowledge base (CLI-friendly alternative to file upload)."""
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if not msg.args:
            await self._reply(msg, Reply(
                text="Usage: /embed <filepath>\n\nExample: /embed /data/docs/manual.pdf",
                format=MessageFormat.PLAIN,
            ))
            return

        filepath = " ".join(msg.args)
        from ids.services.file_processor import extract_text, chunk_text
        try:
            path = Path(filepath)
            if not path.exists():
                await self._reply(msg, Reply(text=f"❌ File not found: {filepath}", format=MessageFormat.PLAIN))
                return
            file_bytes = path.read_bytes()
            text = extract_text(path.name, file_bytes)
            if not text.strip():
                await self._reply(msg, Reply(text=f"⚠️ No extractable text found in: {path.name}", format=MessageFormat.PLAIN))
                return
            chunks = chunk_text(text)
            stored = await self.session_manager.embed_file_chunks(
                project.project_id, path.name, chunks, embedding_model=project.embedding_model
            )
            await self._reply(msg, Reply(
                text=f"✅ *{_esc(path.name)}* embedded — {stored} chunk(s) stored in knowledge base"
            ))
            logger.info("file_embedded_via_embed_cmd", filepath=filepath, project_id=project.project_id, chunks=stored)
        except Exception as e:
            logger.error("embed_cmd_error", error=str(e), filepath=filepath)
            await self._reply(msg, Reply(text=f"❌ Error embedding file: {e}", format=MessageFormat.PLAIN))

    async def cmd_sourcer(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if len(msg.args) < 2:
            await self._reply(msg, Reply(text=(
                "🔍 *Sourcer Mode*\n"
                "Usage: `/sourcer <model> <query>`\n\n"
                "Models: `claude`, `gemini`, `llama` (local)\n"
                "Example: `/sourcer claude what is the current db schema?`\n"
                "Example: `/sourcer llama summarise recent patterns`"
            )))
            return

        VALID_MODELS = ["claude", "gemini", "llama", "local"]
        model_choice = msg.args[0].lower()
        if model_choice not in VALID_MODELS:
            await self._reply(msg, Reply(text="❌ Invalid model. Use `claude`, `gemini`, or `llama`.", format=MessageFormat.PLAIN))
            return

        remaining = msg.args[1:]
        genprompt_model: Optional[str] = None
        if len(remaining) >= 2 and remaining[0].lower() == "-genprompt":
            gp_model = remaining[1].lower()
            if gp_model not in VALID_MODELS:
                await self._reply(msg, Reply(text=f"❌ Invalid genprompt model `{gp_model}`. Use `claude`, `gemini`, or `llama`.", format=MessageFormat.PLAIN))
                return
            genprompt_model = gp_model
            remaining = remaining[2:]

        if not remaining:
            await self._reply(msg, Reply(text="❌ Please provide a query after the model name.", format=MessageFormat.PLAIN))
            return

        query = " ".join(remaining)
        is_local = model_choice in ("llama", "local") or genprompt_model in ("llama", "local")
        label = "Llama (local)" if model_choice in ("llama", "local") else model_choice
        status_parts = [f"🔍 *Sourcer* is analyzing using *{label}*"]
        if genprompt_model:
            status_parts.append(f"🧠 Prompt generator: *{genprompt_model}*")
        if is_local:
            status_parts.append("⏳ This may take several minutes...")
        await self._reply(msg, Reply(text="\n".join(p for p in status_parts if p)))

        keep_typing = None
        try:
            if is_local:
                keep_typing = self.adapter.make_keep_typing_task(msg.user.chat_id)
            else:
                await self.adapter.show_typing(msg.user.chat_id)
            response, generated_prompt = await self.session_manager.run_sourcer(
                project_id=project.project_id,
                task=query,
                model=model_choice,
                genprompt_model=genprompt_model,
                user_id=user_id,
            )

            CHUNK = 4000
            if generated_prompt:
                await self._reply(msg, Reply(text="🧠 *Generated search prompt:*"))
                for i in range(0, len(generated_prompt), CHUNK):
                    await self._reply(msg, Reply(text=generated_prompt[i:i + CHUNK], format=MessageFormat.PLAIN))

            await self._reply(msg, Reply(text=f"📝 *Sourcer Response* ({label})\n━━━━━━━━━━━━━━━━━━━━"))
            for i in range(0, len(response), CHUNK):
                await self._reply(msg, Reply(text=response[i:i + CHUNK], format=MessageFormat.PLAIN))

        except Exception as e:
            logger.error("sourcer_error", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Sourcer Error: {e}", format=MessageFormat.PLAIN))
        finally:
            if keep_typing is not None:
                keep_typing.cancel()

    async def cmd_code(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="⚠️ No active project. Use /project <name> first.", format=MessageFormat.PLAIN))
            return
        if not self.code_workflow:
            await self._reply(msg, Reply(text="⚠️ Code workflow is not configured.", format=MessageFormat.PLAIN))
            return
        if not settings.claude_code_enabled:
            await self._reply(msg, Reply(text="⚠️ Claude Code integration is disabled.", format=MessageFormat.PLAIN))
            return

        task_desc = " ".join(msg.args) if msg.args else ""
        if not task_desc:
            await self._reply(msg, Reply(text="📝 Usage: /code <description>\n\nExample: /code Add Redis caching to vessel.py", format=MessageFormat.PLAIN))
            return

        project_path = Path(settings.projects_root) / project.name
        if not project_path.exists():
            await self._reply(msg, Reply(text=f"⚠️ Project directory not found: {project_path}", format=MessageFormat.PLAIN))
            return

        await self._reply(msg, Reply(text=(
            f"🚀 *Implementing:* {_esc(task_desc)}\n\nClaude Code is working on it..."
        )))
        await self.adapter.show_typing(msg.user.chat_id)

        try:
            result = await self.code_workflow.implement_direct(task_desc, project_path)
            await self._reply(msg, Reply(text=self._format_implementation_result(result)))
        except Exception as e:
            logger.error("code_command_error", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Error: {e}", format=MessageFormat.PLAIN))

    async def cmd_analyze(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="⚠️ No active project. Use /project <name> first.", format=MessageFormat.PLAIN))
            return

        filepath = " ".join(msg.args) if msg.args else ""
        if not filepath:
            await self._reply(msg, Reply(text="📝 Usage: /analyze <filepath>\n\nExample: /analyze app/database/vessels.py", format=MessageFormat.PLAIN))
            return

        await self._reply(msg, Reply(text=f"🔍 Analyzing: {filepath}\n\n⏳ Analyzing...", format=MessageFormat.PLAIN))
        await self._reply(msg, Reply(text="✅ Analysis complete!\n\nFull analysis integration coming soon.", format=MessageFormat.PLAIN))

    async def cmd_validate(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="⚠️ No active project. Use /project <name> first.", format=MessageFormat.PLAIN))
            return

        await self._reply(msg, Reply(text="🔍 Running validation...\n\n⏳ Validating...", format=MessageFormat.PLAIN))
        await self._reply(msg, Reply(text="✅ *Validation Results*\n\nValidation integration coming soon."))

    async def cmd_export(self, msg: Message) -> None:
        user_id = msg.user.user_id
        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        # /export sourcer
        if msg.args and msg.args[0].lower() == "sourcer":
            logs = await self.session_manager.session_store.get_sourcer_logs(project.project_id, limit=1)
            if not logs:
                await self._reply(msg, Reply(text="No sourcer logs found for this project.", format=MessageFormat.PLAIN))
                return
            log = logs[0]
            json_str = log.model_dump_json(indent=2)
            await self.adapter.send_file(
                msg.user.chat_id,
                Attachment(filename=f"sourcer_{log.log_id}.json", data=json_str.encode("utf-8")),
                caption=(
                    f"🔍 Sourcer Log: {log.log_id}\n"
                    f"Model: {log.sourcer_model}"
                    + (f" | GenPrompt: {log.genprompt_model}" if log.genprompt_model else "")
                    + f"\nQuery: {log.original_query[:80]}{'...' if len(log.original_query) > 80 else ''}"
                ),
            )
            return

        session = None
        if msg.args:
            try:
                session_num = int(msg.args[0])
                sessions = await self.session_manager.session_store.get_user_sessions(user_id, project.project_id, limit=20)
                if not sessions:
                    await self._reply(msg, Reply(text="No past sessions found.", format=MessageFormat.PLAIN))
                    return
                if session_num < 1 or session_num > len(sessions):
                    await self._reply(msg, Reply(text=f"❌ Session number must be between 1 and {len(sessions)}", format=MessageFormat.PLAIN))
                    return
                session = sessions[session_num - 1]
            except ValueError:
                await self._reply(msg, Reply(text="❌ valid session number required (e.g. /export 1)", format=MessageFormat.PLAIN))
                return
        else:
            session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
            if not session:
                sessions = await self.session_manager.session_store.get_user_sessions(user_id, project.project_id, limit=1)
                if sessions:
                    session = sessions[0]
                else:
                    await self._reply(msg, Reply(text="No specific session request and no active/recent session found.\nUse /history to see past sessions.", format=MessageFormat.PLAIN))
                    return

        await self._reply(msg, Reply(text=f"📦 Exporting session {session.session_id}...", format=MessageFormat.PLAIN))
        try:
            json_str = session.model_dump_json(indent=2)
            await self.adapter.send_file(
                msg.user.chat_id,
                Attachment(filename=f"session_{session.session_id}.json", data=json_str.encode("utf-8")),
                caption=f"📊 Session Export: {session.session_id}\nStatus: {session.status.value}",
            )
            logger.info("session_exported", session_id=session.session_id, user_id=user_id)
        except Exception as e:
            logger.error("export_failed", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Export failed: {e}", format=MessageFormat.PLAIN))

    async def cmd_daily_update(self, msg: Message) -> None:
        if not self.adapter.is_authorized(msg.user):
            return
        if not self.daily_update_service:
            await self._reply(msg, Reply(text="❌ Daily update service not configured.", format=MessageFormat.PLAIN))
            return

        target_date = date.today()
        model = "gemini"
        redo = False
        for arg in msg.args:
            arg_l = arg.lower()
            if arg_l == "redo":
                redo = True
            elif arg_l in ("claude", "gemini"):
                model = arg_l
            else:
                try:
                    target_date = date.fromisoformat(arg)
                except ValueError:
                    await self._reply(msg, Reply(text=(
                        "❌ Invalid argument. Usage:\n"
                        "`/daily_update [YYYY-MM-DD] [claude|gemini] [redo]`"
                    )))
                    return

        date_str = target_date.isoformat()

        if not redo:
            existing = await self.daily_update_service.fingerprint_store.get(date_str)
            if existing:
                await self._reply(msg, Reply(text=(
                    f"📋 Fingerprint for *{_esc(date_str)}* already exists. Showing stored record:\n"
                    f"_Use_ `/daily_update {date_str} redo` _to overwrite._"
                )))
                await self._send_fingerprint(msg, existing)
                return

        action_label = "Re-collecting" if redo else "Collecting"
        await self._reply(msg, Reply(text=(
            f"🌍 {action_label} planetary fingerprint for *{_esc(date_str)}* via {model.capitalize()}..."
        )))

        try:
            doc = await self.daily_update_service.run(target_date, model=model)
            stored_label = "updated" if redo else "stored"
            await self._reply(msg, Reply(text=f"✅ *Planetary Fingerprint {stored_label} for {_esc(date_str)}*"))
            await self._send_fingerprint(msg, doc)
        except Exception as e:
            logger.error("daily_update_failed", error=str(e), date=date_str)
            await self._reply(msg, Reply(text=f"❌ Daily update failed: {_esc(str(e)[:300])}", format=MessageFormat.PLAIN))

    # ------------------------------------------------------------------
    # Message handling (non-command text)
    # ------------------------------------------------------------------

    async def handle_message(self, msg: Message) -> None:
        """Handle incoming non-command text messages."""
        user_id = msg.user.user_id
        if not self.adapter.is_authorized(msg.user):
            return

        project = self._get_project(user_id)

        # Awaiting comment (feedback for next round)
        if self.awaiting_comment.get(user_id):
            if project:
                session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                if session:
                    session.context = f"{session.context}\n\nUser Comment: {msg.text}"
                    await self.session_manager.session_store.update_session(session)
                    await self.session_manager.learn_from_text(project.project_id, f"Context (User Feedback): {msg.text}", embedding_model=project.embedding_model)
                    self.awaiting_comment[user_id] = False
                    await self._reply(msg, Reply(text="✅ Comment added for the next round! Click 'Continue' when ready.", format=MessageFormat.PLAIN))
                    return
            self.awaiting_comment[user_id] = False

        # Awaiting learn
        if self.awaiting_learn.get(user_id):
            if project:
                await self.session_manager.learn_from_text(project.project_id, msg.text, embedding_model=project.embedding_model)
                self.awaiting_learn[user_id] = False
                await self._reply(msg, Reply(text=f"📝 Added to knowledge base for project: *{_esc(project.name)}*"))
                return
            else:
                self.awaiting_learn[user_id] = False
                await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
                return

        # URL-only → embed
        if msg.is_url_only and msg.urls:
            if not project:
                await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
                return
            await self._reply(msg, Reply(text=f"📥 Downloading {len(msg.urls)} file(s) in background...", format=MessageFormat.PLAIN))
            for url in msg.urls:
                asyncio.create_task(self._process_url_background(url, project.project_id, msg.user.chat_id, project.embedding_model))
            return

        # Standard deliberation
        if not project:
            if not msg.text.startswith("/"):
                await self._reply(msg, Reply(text="❌ No active project selected. Use /project.", format=MessageFormat.PLAIN))
            return

        session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
        if session:
            if session.status == SessionStatus.DEAD_END:
                await self._handle_dead_end_feedback(msg, session, msg.text)
            else:
                await self._reply(msg, Reply(text="⚠️ You have an active session. Use /cancel to cancel it first.", format=MessageFormat.PLAIN))
            return

        if not msg.text.startswith("/"):
            await self._start_deliberation(msg, msg.text, project)

    async def handle_document(self, msg: Message) -> None:
        """Handle file uploads — extract and embed into knowledge base."""
        user_id = msg.user.user_id
        if not self.adapter.is_authorized(msg.user):
            return

        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="❌ No active project. Please use /project first.", format=MessageFormat.PLAIN))
            return

        if not msg.attachments:
            return

        att = msg.attachments[0]
        await self._reply(msg, Reply(text=f"📄 Processing *{_esc(att.filename)}*..."))

        try:
            from ids.services.file_processor import extract_text, chunk_text
            text = extract_text(att.filename, att.data)
            if not text.strip():
                await self._reply(msg, Reply(text="⚠️ No text could be extracted from the file.", format=MessageFormat.PLAIN))
                return

            chunks = chunk_text(text)
            stored = await self.session_manager.embed_file_chunks(
                project_id=project.project_id,
                filename=att.filename,
                chunks=chunks,
                embedding_model=project.embedding_model,
            )

            await self._reply(msg, Reply(text=(
                f"✅ *File embedded into knowledge base*\n\n"
                f"• File: `{_esc(att.filename)}`\n"
                f"• Chunks stored: {stored}\n"
                f"• Project: *{_esc(project.name)}*\n\n"
                f"Use `/sourcer` to query the knowledge base."
            )))
            logger.info("document_embedded", user_id=user_id, filename=att.filename, project_id=project.project_id, chunks=stored)

        except ValueError as e:
            await self._reply(msg, Reply(text=f"❌ {e}", format=MessageFormat.PLAIN))
        except Exception as e:
            logger.error("document_embed_error", error=str(e), filename=att.filename)
            await self._reply(msg, Reply(text=f"❌ Error processing file: {e}", format=MessageFormat.PLAIN))

    async def handle_callback(self, msg: Message) -> None:
        """Handle inline button callbacks."""
        data = msg.callback_data
        if not data:
            return
        user_id = msg.user.user_id

        if data.startswith("delete_project:"):
            parts = data.split(":", 2)
            action, project_id = parts[1], parts[2]
            if action == "cancel":
                await self._reply(msg, Reply(text="❌ Deletion cancelled.", format=MessageFormat.PLAIN, edit_message=True))
            elif action == "confirm":
                await self._reply(msg, Reply(text="🗑️ Deleting project data...", format=MessageFormat.PLAIN, edit_message=True))
                try:
                    summary = await self.session_manager.delete_project(project_id)
                    for uid, proj in list(self.user_projects.items()):
                        if proj.project_id == project_id:
                            del self.user_projects[uid]
                    await self._reply(msg, Reply(text=(
                        f"✅ *Project deleted*\n\n"
                        f"• Sessions removed: {summary['sessions_deleted']}\n"
                        f"• Vector data cleared\n\n"
                        f"Use /register\\_project to start fresh."
                    ), edit_message=True))
                except Exception as e:
                    logger.error("project_delete_error", error=str(e))
                    await self._reply(msg, Reply(text=f"❌ Delete failed: {e}", format=MessageFormat.PLAIN, edit_message=True))
            return

        if data.startswith("dead_end:"):
            action = data.split(":")[1]
            if action == "feedback":
                await self._reply(msg, Reply(text=(
                    "Please send your feedback as a message.\n\n"
                    "You can:\n"
                    "• Provide additional context\n"
                    "• Choose between approaches\n"
                    "• Suggest new direction"
                ), format=MessageFormat.PLAIN, edit_message=True))
            elif action == "restart":
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await self._reply(msg, Reply(text="Restarting deliberation...\nPlease provide new direction or clarification.", format=MessageFormat.PLAIN, edit_message=True))

        elif data.startswith("fingerprint_json:"):
            date_str = data.split(":", 1)[1]
            await self._send_fingerprint_json_file(msg, date_str)

        elif data.startswith("implement:"):
            session_id = data.split(":", 1)[1]
            await self._handle_implement(msg, user_id, session_id)

        elif data.startswith("session:"):
            action = data.split(":")[1]
            if action == "cancel":
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await self.session_manager.cancel_session(session.session_id)
                        await self._reply(msg, Reply(text="❌ Session cancelled.", format=MessageFormat.PLAIN, edit_message=True))
            elif action == "continue":
                project = self._get_project(user_id)
                if project:
                    session = await self.session_manager.session_store.get_active_session(user_id, project.project_id)
                    if session:
                        await self._handle_continuation(msg, session)
            elif action == "comment":
                self.awaiting_comment[user_id] = True
                await self._reply(msg, Reply(text="💬 Please send your comment/feedback. It will be added to the next round's context.", format=MessageFormat.PLAIN))

    async def handle_unknown_command(self, msg: Message) -> None:
        command = msg.text.split()[0] if msg.text else "unknown"
        await self._reply(msg, Reply(text=(
            f"❓ Unknown command: `{command}`\n"
            f"Use /help to see all available commands."
        )))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process_url_background(self, url: str, project_id: str, chat_id: int, embedding_model: str) -> None:
        from ids.services.file_processor import download_url, extract_text, chunk_text
        try:
            filename, file_bytes = await download_url(url)
            text = extract_text(filename, file_bytes)
            if not text.strip():
                await self.adapter.send(chat_id, Reply(text=f"⚠️ `{_esc(url)}` — no extractable text found"))
                return
            chunks = chunk_text(text)
            stored = await self.session_manager.embed_file_chunks(project_id, filename, chunks, embedding_model=embedding_model)
            await self.adapter.send(chat_id, Reply(text=f"✅ *{_esc(filename)}* embedded — {stored} chunk(s)"))
            logger.info("url_embedded", url=url, filename=filename, project_id=project_id, chunks=stored)
        except ValueError as e:
            await self.adapter.send(chat_id, Reply(text=f"❌ `{_esc(url)}` — {_esc(str(e))}"))
            logger.warning("url_embed_rejected", url=url, error=str(e))
        except Exception as e:
            await self.adapter.send(chat_id, Reply(text=f"❌ `{_esc(url)}` — unexpected error: {_esc(str(e))}"))
            logger.error("url_embed_error", url=url, error=str(e))

    async def _start_deliberation(self, msg: Message, text: str, project: Project) -> None:
        user_id = msg.user.user_id
        chat_id = msg.user.chat_id

        sc = len(set(project.specialist_prompt_urls) | set(project.specialist_prompts))
        if sc == 0:
            await self._reply(msg, Reply(text=(
                "⚠️ No specialists configured for this project.\n\n"
                "Add at least one specialist with:\n"
                "`/set_prompts specialist1 <url>`"
            )))
            return

        await self._reply(msg, Reply(text=(
            f"🏛️ *Starting Parliament deliberation...*\n"
            f"Parliament size: {sc} specialist(s)"
        )))

        session = await self.session_manager.create_session(
            user_id=user_id,
            chat_id=chat_id,
            task=text,
            project_id=project.project_id,
            project_name=project.name,
        )

        progress_cb = self.adapter.make_progress_callback(chat_id)

        try:
            await self.adapter.show_typing(chat_id)
            session = await self.session_manager.run_deliberation(session, progress_callback=progress_cb)
            await self._send_session_status_update(msg, session)
        except Exception as e:
            logger.error("deliberation_error", error=str(e), session_id=session.session_id)
            await self._reply(msg, Reply(text=f"❌ Error during deliberation:\n{e}", format=MessageFormat.PLAIN))

    async def _handle_dead_end_feedback(self, msg: Message, session, feedback: str) -> None:
        await self._reply(msg, Reply(text="📝 Processing your feedback...", format=MessageFormat.PLAIN))
        await self.session_manager.handle_user_feedback(session.session_id, feedback, restart=False)
        progress_cb = self.adapter.make_progress_callback(msg.user.chat_id)

        try:
            session = await self.session_manager.continue_session(session.session_id, progress_callback=progress_cb)
            await self._send_session_status_update(msg, session)
        except Exception as e:
            logger.error("continue_error", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Error: {e}", format=MessageFormat.PLAIN))

    async def _handle_continuation(self, msg: Message, session) -> None:
        progress_cb = self.adapter.make_progress_callback(msg.user.chat_id)
        try:
            session = await self.session_manager.run_deliberation(session, progress_callback=progress_cb)
            await self._send_session_status_update(msg, session)
        except Exception as e:
            logger.error("continue_error", error=str(e))
            await self._reply(msg, Reply(text=f"❌ Error: {e}", format=MessageFormat.PLAIN))

    async def _handle_implement(self, msg: Message, user_id: int, session_id: str) -> None:
        if not self.code_workflow or not settings.claude_code_enabled:
            await self._reply(msg, Reply(text="⚠️ Claude Code integration is not available.", format=MessageFormat.PLAIN, edit_message=True))
            return

        project = self._get_project(user_id)
        if not project:
            await self._reply(msg, Reply(text="⚠️ No active project selected.", format=MessageFormat.PLAIN, edit_message=True))
            return

        project_path = Path(settings.projects_root) / project.name
        if not project_path.exists():
            await self._reply(msg, Reply(text=f"⚠️ Project directory not found: {project_path}", format=MessageFormat.PLAIN, edit_message=True))
            return

        session = await self.session_manager.session_store.get_session(session_id)
        if not session:
            await self._reply(msg, Reply(text="⚠️ Session not found.", format=MessageFormat.PLAIN, edit_message=True))
            return

        await self._reply(msg, Reply(text="🚀 *Implementing consensus...*\n\nClaude Code is working on it...", edit_message=True))
        await self.adapter.show_typing(msg.user.chat_id)

        try:
            result = await self.code_workflow.implement_from_consensus(session, project_path)
            await self._reply(msg, Reply(text=self._format_implementation_result(result)))
        except Exception as e:
            logger.error("implement_error", error=str(e), session_id=session_id)
            await self._reply(msg, Reply(text=f"❌ Implementation error: {e}", format=MessageFormat.PLAIN))

    async def _send_session_status_update(self, msg: Message, session) -> None:
        if session.status == SessionStatus.CONSENSUS:
            text = self._format_consensus_decision(session)
            buttons = []
            if self.code_workflow and settings.claude_code_enabled:
                project = self._get_project(session.user_id)
                if project:
                    buttons = [[Button("🚀 Implement", f"implement:{session.session_id}")]]
            await self._reply(msg, Reply(text=text, buttons=buttons))

        elif session.status == SessionStatus.DEAD_END:
            text = self._format_dead_end(session)
            await self._reply(msg, Reply(text=text, buttons=[
                [Button("💬 Provide Feedback", "dead_end:feedback")],
                [Button("🔄 Restart Fresh", "dead_end:restart")],
                [Button("❌ Cancel", "session:cancel")],
            ]))

        elif session.status == SessionStatus.AWAITING_CONTINUATION:
            text = self._format_round_update(session.rounds[-1])
            await self._reply(msg, Reply(text=text, buttons=[
                [Button("✅ Continue", "session:continue"), Button("💬 Add Comment", "session:comment")],
                [Button("❌ Cancel", "session:cancel")],
            ]))

    # ------------------------------------------------------------------
    # Formatting (interface-agnostic — Markdown)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_consensus_decision(session) -> str:
        if not session.rounds:
            return "No deliberation rounds found."
        last_round = session.rounds[-1]
        merged = last_round.merged_cross
        return "".join([
            "✅ *CONSENSUS REACHED*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "*Final Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
            f"*Decision:*\n{_esc(last_round.generalist_response.response)}\n\n",
            f"📝 Completed in {len(session.rounds)} round(s)",
        ])

    @staticmethod
    def _format_dead_end(session) -> str:
        if not session.rounds:
            return "Session has no rounds."
        last_round = session.rounds[-1]
        merged = last_round.merged_cross
        if merged.std_confidence < 10:
            agreement = "🎯 High Agreement"
        elif merged.std_confidence < 20:
            agreement = "👍 Good Agreement"
        else:
            agreement = "⚠️ Divergent Views"
        content = last_round.generalist_response.response.replace("```", "'''")
        return "".join([
            f"⚠️ *Round {last_round.round_number} — Dead End*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "*Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
            f"*Status:* {agreement}\n\n",
            f"*{last_round.generalist_response.role_name} Synthesis:*\n",
            f"```\n{content}\n```\n\n",
            "Please provide guidance to continue:\n"
            "• Additional context\n"
            "• Preference between approaches\n"
            "• New direction to explore",
        ])

    @staticmethod
    def _format_round_update(round_result) -> str:
        merged = round_result.merged_cross
        if merged.std_confidence < 10:
            agreement = "🎯 High Agreement"
        elif merged.std_confidence < 20:
            agreement = "👍 Good Agreement"
        else:
            agreement = "⚠️ Divergent Views"
        content = round_result.generalist_response.response.replace("```", "'''")
        return "".join([
            f"📊 *Round {round_result.round_number} Complete*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "*Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
            f"*Status:* {agreement}\n\n",
            f"*{round_result.generalist_response.role_name} Synthesis:*\n",
            f"```\n{content}\n```",
        ])

    @staticmethod
    def _format_implementation_result(result) -> str:
        status = "✅ *IMPLEMENTATION COMPLETE*" if result.success else "❌ *IMPLEMENTATION FAILED*"
        parts = [f"{status}\n", "━━━━━━━━━━━━━━━━━━━━\n\n"]
        if result.result_text:
            text = result.result_text
            if len(text) > 3000:
                text = text[:3000] + "\n\n... (truncated)"
            text = text.replace("```", "'''")
            parts.append(f"*Result:*\n```\n{text}\n```\n\n")
        if result.error_message:
            parts.append(f"*Error:* {_esc(result.error_message)}\n\n")
        parts.append(
            f"*Stats:*\n"
            f"• Turns: {result.num_turns}\n"
            f"• Cost: ${result.cost_usd:.4f}\n"
            f"• Duration: {result.duration_ms / 1000:.1f}s\n"
        )
        return "".join(parts)

    async def _send_fingerprint(self, msg: Message, doc: dict) -> None:
        """Send formatted fingerprint data."""
        def fmt_val(v) -> str:
            if isinstance(v, list):
                return ", ".join(str(i) for i in v) if v else "—"
            return str(v)

        def fmt_flat_dict(data: dict, indent: str = "  ") -> list:
            lines = []
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                label = k.replace("_", " ").title()
                if isinstance(v, dict):
                    lines.append(f"{indent}*{_esc(label)}*")
                    for sk, sv in v.items():
                        if sk.startswith("_"):
                            continue
                        slabel = sk.replace("_", " ").title()
                        lines.append(f"{indent}  • {_esc(slabel)}: `{_esc(fmt_val(sv))}`")
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    lines.append(f"{indent}*{_esc(label)}*")
                    for item in v:
                        summary = ", ".join(f"{ik}={iv}" for ik, iv in item.items() if not str(ik).startswith("_"))
                        lines.append(f"{indent}  • `{_esc(summary[:120])}`")
                else:
                    lines.append(f"{indent}• {_esc(label)}: `{_esc(fmt_val(v))}`")
            return lines

        sections = []
        for section_key, emoji, title in [
            ("solar", "☀️", "Solar"),
            ("lunar", "🌙", "Lunar"),
            ("planetary", "🪐", "Planetary"),
            ("geomagnetic", "🧲", "Geomagnetic"),
            ("atmospheric", "🌬️", "Atmospheric (Mediterranean)"),
            ("tides", "🌊", "Tides"),
            ("seismic", "🌋", "Seismic"),
        ]:
            data = doc.get(section_key, {})
            if data:
                lines = [f"{emoji} *{title}*"] + fmt_flat_dict(data)
                sections.append("\n".join(lines))

        routes = doc.get("route_corridors", [])
        if routes:
            lines = ["🗺️ *Route Corridors*"]
            route_list = routes if isinstance(routes, list) else list(routes.values())
            for rdata in route_list:
                if isinstance(rdata, dict):
                    name = rdata.get("name") or rdata.get("corridor_id", "?")
                    lines.append(f"  *{_esc(str(name))}*")
                    for k, v in rdata.items():
                        if k.startswith("_") or k in ("name", "corridor_id"):
                            continue
                        label = k.replace("_", " ").title()
                        lines.append(f"    • {_esc(label)}: `{_esc(fmt_val(v))}`")
            sections.append("\n".join(lines))

        components = doc.get("fingerprint_components", {})
        if components:
            lines = ["📊 *Fingerprint Vector (16 dims)*"] + fmt_flat_dict(components)
            sections.append("\n".join(lines))

        meta_parts = []
        if doc.get("updated_at"):
            meta_parts.append(f"updated: `{_esc(str(doc['updated_at']))}`")
        if doc.get("source"):
            meta_parts.append(f"source: `{_esc(doc['source'])}`")
        if doc.get("version"):
            meta_parts.append(f"v`{_esc(str(doc['version']))}`")
        if meta_parts:
            sections.append("💾 *Metadata:* " + " | ".join(meta_parts))

        MAX_LEN = 4000
        chunk = "━━━━━━━━━━━━━━━━━━━━\n"
        for section in sections:
            candidate = chunk + section + "\n\n"
            if len(candidate) > MAX_LEN:
                if chunk.strip():
                    await self._reply(msg, Reply(text=chunk.strip()))
                chunk = section + "\n\n"
            else:
                chunk = candidate
        if chunk.strip():
            await self._reply(msg, Reply(text=chunk.strip()))

        # Download button
        await self._reply(msg, Reply(
            text="Tap to download the full stored document:",
            format=MessageFormat.PLAIN,
            buttons=[[Button("📥 Raw JSON", f"fingerprint_json:{doc['date']}")]],
        ))

    async def _send_fingerprint_json_file(self, msg: Message, date_str: str) -> None:
        import json
        if not self.daily_update_service:
            return
        doc = await self.daily_update_service.fingerprint_store.get(date_str)
        if not doc:
            return
        display_doc = {k: v for k, v in doc.items() if k != "_id"}
        json_bytes = json.dumps(display_doc, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        await self.adapter.send_file(
            msg.user.chat_id,
            Attachment(filename=f"fingerprint_{date_str}.json", data=json_bytes),
            caption=f"📄 Planetary fingerprint — {date_str}",
        )
