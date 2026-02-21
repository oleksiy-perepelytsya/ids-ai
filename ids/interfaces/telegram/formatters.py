"""Formatters for Telegram display"""

from typing import List
from ids.models import RoundResult, AgentResponse, DevSession, Project
from ids.models.code_task import ClaudeCodeResult
from ids.utils import get_logger

logger = get_logger(__name__)


class TelegramFormatter:
    """Format data for beautiful Telegram display"""

    @staticmethod
    def format_consensus_decision(session: DevSession) -> str:
        """Format final consensus decision"""
        if not session.rounds:
            return "No deliberation rounds found."

        last_round = session.rounds[-1]
        merged = last_round.merged_cross

        # Build decision message
        msg_parts = [
            "✅ *CONSENSUS REACHED*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "*Final Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
        ]

        # Generalist synthesis as the decision
        synthesis = last_round.generalist_response.response
        msg_parts.append(f"*Decision:*\n{TelegramFormatter.escape_markdown(synthesis)}\n\n")

        msg_parts.append(f"📝 Completed in {len(session.rounds)} round(s)")

        return "".join(msg_parts)

    @staticmethod
    def format_dead_end(session: DevSession) -> str:
        """Format dead-end message"""
        if not session.rounds:
            return "Session has no rounds."

        last_round = session.rounds[-1]
        merged = last_round.merged_cross

        msg_parts = [
            "⚠️ *DEAD-END REACHED*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "The Parliament couldn't reach consensus.\n\n",
            "*Current State:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
        ]

        # Show each specialist's perspective using role_name
        if last_round.agent_responses:
            msg_parts.append("*Specialist Perspectives:*\n\n")
            for resp in last_round.agent_responses:
                preview = TelegramFormatter.escape_markdown(resp.response[:150])
                msg_parts.append(f"*{resp.role_name}:*\n{preview}...\n\n")

        msg_parts.append(
            "I need your guidance to proceed. Please provide:\n"
            "• Additional context\n"
            "• Preference between approaches\n"
            "• New direction to explore"
        )

        return "".join(msg_parts)

    @staticmethod
    def format_round_update(round_result: RoundResult) -> str:
        """Format round update for user display"""
        merged = round_result.merged_cross

        # Agreement indicator
        if merged.std_confidence < 10:
            agreement = "🎯 High Agreement"
        elif merged.std_confidence < 20:
            agreement = "👍 Good Agreement"
        else:
            agreement = "⚠️ Divergent Views"

        # Escape triple backticks in response to avoid breaking the block
        content = round_result.generalist_response.response.replace("```", "'''")

        msg = [
            f"📊 *Round {round_result.round_number} Complete*\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
            "*Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
            f"*Status:* {agreement}\n\n",
            f"*{round_result.generalist_response.role_name} Synthesis:*\n",
            f"```\n{content}\n```"
        ]

        return "".join(msg)

    @staticmethod
    def format_project_list(projects: List[Project]) -> str:
        """Format list of projects"""
        if not projects:
            return "You have no registered projects.\n\nUse /register_project to create one."

        msg_parts = ["📂 *Your Projects:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]

        for project in projects:
            specialist_count = len(project.specialist_prompt_urls)
            msg_parts.append(f"• *{project.name}*")
            if project.description:
                msg_parts.append(f" — {project.description}")
            msg_parts.append(f"\n  Specialists: {specialist_count} configured\n\n")

        msg_parts.append("Use /project <name> to switch.")

        return "".join(msg_parts)

    @staticmethod
    def format_project_info(project: Project, session_count: int = 0, last_session_date: str = "") -> str:
        """Format detailed project info for /project_info command"""
        esc = TelegramFormatter.escape_markdown
        specialist_count = len(project.specialist_prompt_urls)

        msg_parts = [
            f"📂 *Project: {esc(project.name)}* (`{project.project_id}`)\n",
            "━━━━━━━━━━━━━━━━━━━━\n",
        ]

        if project.description:
            msg_parts.append(f"Description: {esc(project.description)}\n")

        msg_parts.append(f"\n*Parliament ({specialist_count} specialists):*\n")

        if specialist_count == 0:
            msg_parts.append("  No specialists configured yet\\.\n")
        else:
            for key in sorted(project.specialist_prompt_urls.keys(), key=int):
                url = project.specialist_prompt_urls[key]
                msg_parts.append(f"• specialist\\_{key}: `{url}`\n")

        msg_parts.append("\n*Roles:*\n")
        if project.generalist_prompt_url:
            msg_parts.append(f"• Generalist: `{project.generalist_prompt_url}` [max {project.generalist_max_tokens} tokens]\n")
        else:
            msg_parts.append(f"• Generalist: using default [max {project.generalist_max_tokens} tokens]\n")

        if project.sourcer_prompt_url:
            msg_parts.append(f"• Sourcer: `{project.sourcer_prompt_url}` [max {project.sourcer_max_tokens} tokens]\n")
        else:
            msg_parts.append(f"• Sourcer: using default [max {project.sourcer_max_tokens} tokens]\n")

        msg_parts.append(f"• Specialists: max {project.specialist_max_tokens} tokens each\n")

        if session_count > 0:
            msg_parts.append(f"\n*Sessions:* {session_count} total")
            if last_session_date:
                msg_parts.append(f", last: {last_session_date}")
            msg_parts.append("\n")

        msg_parts.append(
            "\n*Configure parliament with:*\n"
            "`/set_prompts specialist1 <url>`\n"
            "`/set_prompts specialist2 <url>`\n"
            "`/set_prompts generalist <url>` (optional)\n"
        )

        return "".join(msg_parts)

    @staticmethod
    def format_session_history(sessions: List[DevSession]) -> str:
        """Format session history"""
        if not sessions:
            return "No previous sessions found for this project."

        msg_parts = ["📜 *Recent Sessions:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]

        for session in sessions[:5]:  # Show last 5
            status_emoji = {
                "consensus": "✅",
                "dead_end": "⚠️",
                "cancelled": "❌",
                "deliberating": "⏳"
            }.get(session.status, "❓")

            task_preview = session.task[:50]
            msg_parts.append(
                f"{status_emoji} {task_preview}...\n"
                f"   ID: `{session.session_id}`\n"
                f"   Status: {session.status}\n"
                f"   Rounds: {len(session.rounds)}\n\n"
            )

        return "".join(msg_parts)

    @staticmethod
    def format_implementation_result(result: ClaudeCodeResult) -> str:
        """Format Claude Code implementation result for Telegram display"""
        if result.success:
            status = "✅ *IMPLEMENTATION COMPLETE*"
        else:
            status = "❌ *IMPLEMENTATION FAILED*"

        msg_parts = [
            f"{status}\n",
            "━━━━━━━━━━━━━━━━━━━━\n\n",
        ]

        if result.result_text:
            # Truncate long results for Telegram (4096 char limit)
            text = result.result_text
            if len(text) > 3000:
                text = text[:3000] + "\n\n... (truncated)"
            # Escape triple backticks to avoid breaking markdown
            text = text.replace("```", "'''")
            msg_parts.append(f"*Result:*\n```\n{text}\n```\n\n")

        if result.error_message:
            msg_parts.append(
                f"*Error:* {TelegramFormatter.escape_markdown(result.error_message)}\n\n"
            )

        msg_parts.append(
            f"*Stats:*\n"
            f"• Turns: {result.num_turns}\n"
            f"• Cost: ${result.cost_usd:.4f}\n"
            f"• Duration: {result.duration_ms / 1000:.1f}s\n"
        )

        return "".join(msg_parts)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for Telegram Markdown (Legacy)"""
        if not text:
            return ""
        # Characters to escape: _ * ` [
        return text.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
