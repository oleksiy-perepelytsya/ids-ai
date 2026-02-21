"""Utility for exporting and viewing full deliberation conversations"""

from typing import List
from ids.models import DevSession, RoundResult


class ConversationExporter:
    """Export deliberation conversations in readable format"""

    @staticmethod
    def export_to_markdown(session: DevSession) -> str:
        """
        Export full conversation to Markdown format.

        Args:
            session: DevSession to export

        Returns:
            Markdown-formatted conversation
        """
        lines = [
            f"# Deliberation Session: {session.session_id}",
            f"",
            f"**User:** {session.telegram_user_id}",
            f"**Project:** {session.project_name or 'General'} (`{session.project_id}`)",
            f"**Created:** {session.created_at.isoformat()}",
            f"**Status:** {session.status.value}",
            f"",
            f"## Task",
            f"",
            f"{session.task}",
            f"",
        ]

        if session.context:
            lines.extend([
                f"## Context / User Guidance",
                f"",
                f"{session.context}",
                f"",
            ])

        # Export each round
        for round_result in session.rounds:
            lines.extend(ConversationExporter._export_round(round_result))

        # Final outcome
        if session.status == "consensus":
            lines.extend([
                f"",
                f"## ✅ Final Outcome: CONSENSUS",
                f"",
                f"Decision reached after {len(session.rounds)} round(s).",
            ])
        elif session.status == "dead_end":
            lines.extend([
                f"",
                f"## ⚠️ Final Outcome: DEAD END",
                f"",
                f"Unable to reach consensus after {len(session.rounds)} round(s).",
            ])

        return "\n".join(lines)

    @staticmethod
    def _export_round(round_result: RoundResult) -> List[str]:
        """Export a single round"""
        generalist = round_result.generalist_response
        lines = [
            f"",
            f"---",
            f"",
            f"## Round {round_result.round_number}",
            f"",
            f"**Time:** {round_result.timestamp.isoformat()}",
            f"",
            f"### Round Summary",
            f"",
            f"```",
            f"{round_result.generalist_prompt}",
            f"```",
            f"",
            f"### Specialist Responses",
            f"",
        ]

        # Each specialist response
        for agent_resp in round_result.agent_responses:
            lines.extend([
                f"#### {agent_resp.role_name}",
                f"",
                f"**CROSS Scores:**",
                f"- Confidence: {agent_resp.cross_score.confidence:.1f}/100",
                f"- Risk: {agent_resp.cross_score.risk:.1f}/100",
                f"- Outcome: {agent_resp.cross_score.outcome:.1f}/100",
                f"",
                f"**Response:**",
                f"```",
                f"{agent_resp.response}",
                f"```",
                f"",
            ])

        # Generalist synthesis
        lines.extend([
            f"### {generalist.role_name} Synthesis",
            f"",
            f"**CROSS Scores:**",
            f"- Confidence: {generalist.cross_score.confidence:.1f}/100",
            f"- Risk: {generalist.cross_score.risk:.1f}/100",
            f"- Outcome: {generalist.cross_score.outcome:.1f}/100",
            f"",
            f"**Synthesis:**",
            f"```",
            f"{generalist.response}",
            f"```",
            f"",
        ])

        # Merged results
        agent_count = len(round_result.agent_responses) + 1  # +1 for generalist
        lines.extend([
            f"### Merged CROSS Scores ({agent_count} Agents)",
            f"",
            f"- **Avg Confidence:** {round_result.merged_cross.avg_confidence:.1f}/100",
            f"- **Max Risk:** {round_result.merged_cross.max_risk:.1f}/100",
            f"- **Avg Outcome:** {round_result.merged_cross.avg_outcome:.1f}/100",
            f"- **Std Confidence:** {round_result.merged_cross.std_confidence:.1f} (agreement)",
            f"- **Std Outcome:** {round_result.merged_cross.std_outcome:.1f} (agreement)",
            f"",
            f"### Round Decision: {round_result.decision.value.upper()}",
            f"",
        ])

        if round_result.decision_reasoning:
            lines.extend([
                f"**Reasoning:**",
                f"{round_result.decision_reasoning}",
                f"",
            ])

        return lines

    @staticmethod
    def export_to_json(session: DevSession) -> dict:
        """
        Export to JSON (using Pydantic's model_dump).

        Args:
            session: DevSession to export

        Returns:
            Dictionary with complete session data
        """
        return session.model_dump()

    @staticmethod
    def get_conversation_summary(session: DevSession) -> str:
        """
        Get brief conversation summary.

        Args:
            session: DevSession to summarize

        Returns:
            Brief text summary
        """
        total_agents = sum(len(r.agent_responses) for r in session.rounds)

        return (
            f"Session {session.session_id}: {session.status.value}\n"
            f"Task: {session.task[:100]}{'...' if len(session.task) > 100 else ''}\n"
            f"Rounds: {len(session.rounds)}\n"
            f"Total specialist responses: {total_agents}\n"
            f"Created: {session.created_at.isoformat()}"
        )
