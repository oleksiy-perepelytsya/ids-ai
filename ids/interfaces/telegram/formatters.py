"""Formatters for Telegram display"""

from typing import List
from ids.models import RoundResult, AgentResponse, CrossScore, DevSession, Project
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
            f"━━━━━━━━━━━━━━━━━━━━\n\n",
            f"*Final Scores:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
        ]
        
        # Add Generalist's recommendation (as the synthesized view)
        generalist_approach = last_round.generalist_cross.explanation
        msg_parts.append(f"*Decision:*\n{generalist_approach}\n\n")
        
        # Add key concerns from all agents
        all_concerns = []
        for resp in last_round.agent_responses:
            all_concerns.extend(resp.concerns)
        
        if all_concerns:
            msg_parts.append("*Key Considerations:*\n")
            # Show top 5 unique concerns
            unique_concerns = list(dict.fromkeys(all_concerns))[:5]
            for concern in unique_concerns:
                msg_parts.append(f"• {concern}\n")
        
        msg_parts.append(f"\n📝 Completed in {len(session.rounds)} round(s)")
        
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
            f"━━━━━━━━━━━━━━━━━━━━\n\n",
            f"The Parliament couldn't reach consensus.\n\n",
            f"*Current State:*\n",
            f"• Confidence: {merged.avg_confidence:.1f}%\n",
            f"• Risk: {merged.max_risk:.1f}%\n",
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n",
        ]
        
        # Show diverging viewpoints
        msg_parts.append("*Diverging Perspectives:*\n\n")
        
        # Group by role type
        dev_views = []
        arch_views = []
        sre_views = []
        
        for resp in last_round.agent_responses:
            if "developer" in resp.agent_id.lower():
                dev_views.append(resp)
            elif "architect" in resp.agent_id.lower():
                arch_views.append(resp)
            elif "sre" in resp.agent_id.lower():
                sre_views.append(resp)
        
        if dev_views:
            msg_parts.append("👨‍💻 *Developer View:*\n")
            msg_parts.append(f"{dev_views[0].proposed_approach[:150]}...\n\n")
        
        if arch_views:
            msg_parts.append("🏗️ *Architect View:*\n")
            msg_parts.append(f"{arch_views[0].proposed_approach[:150]}...\n\n")
        
        if sre_views:
            msg_parts.append("⚙️ *SRE View:*\n")
            msg_parts.append(f"{sre_views[0].proposed_approach[:150]}...\n\n")
        
        msg_parts.append(
            "I need your guidance to proceed. Please provide:\n"
            "• Additional context\n"
            "• Preference between approaches\n"
            "• New direction to explore"
        )
        
        return "".join(msg_parts)
    
    @staticmethod
    def format_round_update(round_result: RoundResult) -> str:
        """Format round update for logging"""
        merged = round_result.merged_cross
        
        # Agreement indicator
        if merged.std_confidence < 10:
            agreement = "🎯 High Agreement"
        elif merged.std_confidence < 20:
            agreement = "👍 Good Agreement"
        else:
            agreement = "⚠️ Divergent Views"
        
        msg = (
            f"📊 *Round {round_result.round_number} Complete*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*Scores:*\n"
            f"• Confidence: {merged.avg_confidence:.1f}%\n"
            f"• Risk: {merged.max_risk:.1f}%\n"
            f"• Outcome: {merged.avg_outcome:.1f}%\n\n"
            f"*Status:* {agreement}\n"
        )
        
        return msg
    
    @staticmethod
    def format_project_list(projects: List[Project]) -> str:
        """Format list of projects"""
        if not projects:
            return "You have no registered projects.\n\nUse /register_project to create one."
        
        msg_parts = ["📂 *Your Projects:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]
        
        for project in projects:
            msg_parts.append(f"• *{project.name}*\n")
            if project.description:
                msg_parts.append(f"  {project.description}\n")
            msg_parts.append("\n")
        
        msg_parts.append("Use /project <name> to switch.")
        
        return "".join(msg_parts)
    
    @staticmethod
    def format_session_history(sessions: List[DevSession]) -> str:
        """Format session history"""
        if not sessions:
            return "No previous sessions found."
        
        msg_parts = ["📜 *Recent Sessions:*\n━━━━━━━━━━━━━━━━━━━━\n\n"]
        
        for session in sessions[:5]:  # Show last 5
            status_emoji = {
                "consensus": "✅",
                "dead_end": "⚠️",
                "cancelled": "❌",
                "deliberating": "⏳"
            }.get(session.status, "❓")
            
            msg_parts.append(
                f"{status_emoji} {session.task[:50]}...\n"
                f"   ID: `{session.session_id}`\n"
                f"   Status: {session.status}\n"
                f"   Rounds: {len(session.rounds)}\n\n"
            )
        
        return "".join(msg_parts)
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
