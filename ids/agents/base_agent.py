"""Unified agent implementation - all agents use this class with different system prompts"""

import re
from typing import Dict, List, Optional
from ids.models import AgentResponse, CrossScore, ROLE_GENERALIST, ROLE_SOURCER
from ids.services import LLMClient
from ids.utils import get_logger

logger = get_logger(__name__)


class Agent:
    """
    Unified agent class. All agents (Generalist + specialists) use this.
    Differentiation comes from the system_prompt passed at construction.
    """

    def __init__(self, role_id: str, system_prompt: str, llm_client: LLMClient, max_tokens: int = 1000):
        self.role_id = role_id
        self.system_prompt = system_prompt
        self.role_name = self._extract_role_name(system_prompt)
        self.llm_client = llm_client
        self.max_tokens = max_tokens
        self._is_generalist = (role_id == ROLE_GENERALIST)
        logger.info("agent_initialized", role_id=role_id, role_name=self.role_name)

    def _extract_role_name(self, prompt: str) -> str:
        """Extract role name from '# Role: <name>' header in the system prompt."""
        match = re.search(r'^#\s*Role:\s*(.+)', prompt, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: prettify the role_id
        return self.role_id.replace('_', ' ').title()

    async def analyze(
        self,
        task: str,
        context: str = "",
        specialist_responses: Optional[List[AgentResponse]] = None,
        previous_rounds_summary: Optional[List[Dict]] = None,
        learning_patterns: Optional[List[Dict]] = None,
        model_override: Optional[str] = None
    ) -> AgentResponse:
        """
        Analyze task and provide CROSS scoring + free-text response.

        Args:
            task: The question/task to analyze
            context: Additional context about the task
            specialist_responses: For generalist: list of specialist AgentResponses this round
            previous_rounds_summary: History of previous deliberation rounds
            learning_patterns: Relevant context found in vector DB
            model_override: Specific model to use (for Sourcer mode)

        Returns:
            AgentResponse with CROSS scores and analysis
        """
        if self._is_generalist:
            prompt = self._build_generalist_prompt(task, context, specialist_responses, previous_rounds_summary, learning_patterns)
        else:
            prompt = self._build_specialist_prompt(task, context, previous_rounds_summary, learning_patterns)

        # Call appropriate LLM
        if model_override:
            response_text = await self.llm_client.call_model(
                model=model_override,
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
                max_tokens=self.max_tokens
            )
        elif self._is_generalist:
            response_text = await self.llm_client.call_claude(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
                max_tokens=self.max_tokens
            )
        else:
            response_text = await self.llm_client.call_gemini(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
                max_tokens=self.max_tokens
            )

        # Parse response
        cross_score, response_body = self._parse_response(response_text)

        agent_response = AgentResponse(
            agent_id=self.role_id,
            role_name=self.role_name,
            cross_score=cross_score,
            response=response_body
        )

        logger.info(
            "agent_analysis_complete",
            role_id=self.role_id,
            role_name=self.role_name,
            confidence=cross_score.confidence,
            risk=cross_score.risk,
            outcome=cross_score.outcome
        )

        return agent_response

    def _build_specialist_prompt(
        self,
        task: str,
        context: str,
        previous_rounds_summary: Optional[List[Dict]],
        learning_patterns: Optional[List[Dict]] = None
    ) -> str:
        """Build the prompt for a specialist agent."""
        parts = []

        parts.append(f"TASK:\n{task}\n")

        if context:
            parts.append(f"\nADDITIONAL CONTEXT:\n{context}\n")

        if learning_patterns:
            parts.append("\nRELEVANT KNOWLEDGE BASE PATTERNS:\n")
            for i, pattern in enumerate(learning_patterns, 1):
                parts.append(f"Pattern {i}: {pattern.get('content')}\n")

        if previous_rounds_summary:
            parts.append("\nPREVIOUS DELIBERATION ROUNDS:\n")
            for round_data in previous_rounds_summary:
                parts.append(self._format_round_summary(round_data))

        parts.append(
            "\nProvide your analysis in exactly this format:\n\n"
            "CROSS SCORES:\n"
            "Confidence: [0-100]\n"
            "Risk: [0-100]\n"
            "Outcome: [0-100]\n\n"
            "RESPONSE:\n"
            "[Your detailed analysis and recommendation]"
        )

        return "\n".join(parts)

    def _build_generalist_prompt(
        self,
        task: str,
        context: str,
        specialist_responses: Optional[List[AgentResponse]],
        previous_rounds_summary: Optional[List[Dict]],
        learning_patterns: Optional[List[Dict]] = None
    ) -> str:
        """Build the prompt for the generalist agent, synthesizing specialist input."""
        parts = []

        parts.append(f"TASK:\n{task}\n")

        if context:
            parts.append(f"\nADDITIONAL CONTEXT:\n{context}\n")

        if learning_patterns:
            parts.append("\nRELEVANT KNOWLEDGE BASE PATTERNS:\n")
            for i, pattern in enumerate(learning_patterns, 1):
                parts.append(f"Pattern {i}: {pattern.get('content')}\n")

        if previous_rounds_summary:
            parts.append("\nPREVIOUS DELIBERATION ROUNDS:\n")
            for round_data in previous_rounds_summary:
                parts.append(self._format_round_summary(round_data))

        if specialist_responses:
            parts.append("\nSPECIALIST PERSPECTIVES THIS ROUND:\n")
            for resp in specialist_responses:
                c = resp.cross_score.confidence
                r = resp.cross_score.risk
                o = resp.cross_score.outcome
                parts.append(
                    f"{resp.role_name} [C:{c:.0f}, R:{r:.0f}, O:{o:.0f}]:\n"
                    f"{resp.response}\n"
                )

        parts.append(
            "\nSynthesize the specialist perspectives above and provide your consolidated analysis.\n"
            "Do NOT repeat each specialist's view verbatim — synthesize into a coherent recommendation.\n\n"
            "Provide your synthesis in exactly this format:\n\n"
            "CROSS SCORES:\n"
            "Confidence: [0-100]\n"
            "Risk: [0-100]\n"
            "Outcome: [0-100]\n\n"
            "RESPONSE:\n"
            "[Your synthesized analysis and recommendation for the user]"
        )

        return "\n".join(parts)

    def _format_round_summary(self, round_data: Dict) -> str:
        """Format a previous round for inclusion in the prompt."""
        parts = [f"\nRound {round_data.get('round_number', '?')}:"]

        if "merged_cross" in round_data:
            merged = round_data["merged_cross"]
            parts.append(
                f"  Avg Confidence: {merged.get('avg_confidence', 0):.1f}, "
                f"Max Risk: {merged.get('max_risk', 0):.1f}, "
                f"Avg Outcome: {merged.get('avg_outcome', 0):.1f}"
            )

        if "agent_responses" in round_data:
            for resp in round_data["agent_responses"]:
                role = resp.get("role_name", resp.get("agent_id", "Unknown"))
                response_text = resp.get("response", "")[:150]
                parts.append(f"  {role}: {response_text}...")

        return "\n".join(parts) + "\n"

    def _parse_response(self, response_text: str) -> tuple[CrossScore, str]:
        """
        Parse CROSS scores and response body from LLM output.

        Returns:
            (CrossScore, response_body_str)
        """
        try:
            confidence_match = re.search(r"Confidence:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)
            risk_match = re.search(r"Risk:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)
            outcome_match = re.search(r"Outcome:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)

            if not all([confidence_match, risk_match, outcome_match]):
                logger.warning("failed_to_parse_cross_scores", role_id=self.role_id, response_preview=response_text[:200])
                cross_score = CrossScore(confidence=50.0, risk=50.0, outcome=50.0)
            else:
                cross_score = CrossScore(
                    confidence=float(confidence_match.group(1)),
                    risk=float(risk_match.group(1)),
                    outcome=float(outcome_match.group(1))
                )

            # Extract everything after RESPONSE:
            response_match = re.search(r"RESPONSE:\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)
            if response_match:
                response_body = response_match.group(1).strip()
            else:
                # Fallback: use whole text minus the CROSS SCORES block
                response_body = re.sub(
                    r"CROSS SCORES:.*?(?=\n\n|\Z)", "", response_text, flags=re.DOTALL | re.IGNORECASE
                ).strip()
                if not response_body:
                    response_body = response_text.strip()

            return cross_score, response_body

        except Exception as e:
            logger.error("response_parsing_error", role_id=self.role_id, error=str(e))
            return CrossScore(confidence=50.0, risk=50.0, outcome=50.0), response_text.strip()
