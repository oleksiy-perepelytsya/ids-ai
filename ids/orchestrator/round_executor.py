"""Round executor - executes a single deliberation round"""

import asyncio
from typing import List, Optional, Dict
from ids.models import AgentResponse, RoundResult, DecisionResult, DevSession, ROLE_GENERALIST, ROLE_SOURCER
from ids.agents import Agent
from ids.orchestrator.consensus_builder import ConsensusBuilder
from ids.utils import get_logger

logger = get_logger(__name__)


class RoundExecutor:
    """Executes a single deliberation round with all agents"""

    def __init__(
        self,
        agents: dict,  # Dict[str, Agent]
        consensus_builder: ConsensusBuilder,
        chroma_store: Optional[object] = None
    ):
        self.agents = agents
        self.consensus_builder = consensus_builder
        self.chroma_store = chroma_store
        logger.info("round_executor_initialized", agent_count=len(agents))

    async def execute_round(
        self,
        session: DevSession,
        round_num: int
    ) -> RoundResult:
        """
        Execute a deliberation round.

        Uniform flow (every round):
        1. RAG: retrieve learning patterns from ChromaDB
        2. Specialists analyze (parallel or sequential)
        3. Generalist synthesizes specialist responses
        4. Merge CROSS scores (all agents)
        5. ConsensusBuilder evaluates
        """
        logger.info("round_started", session_id=session.session_id, round_num=round_num)

        # Step 1: RAG retrieval
        learning_patterns = []
        if self.chroma_store:
            learning_patterns = await self.chroma_store.search_learning_patterns(
                project_id=session.project_id,
                query=session.task
            )
            logger.info("rag_context_retrieved", count=len(learning_patterns))

        # Step 2: Prepare round history
        previous_rounds_summary = self._prepare_round_history(session)

        # Step 3: Run specialists
        specialist_role_ids = [
            k for k in self.agents
            if k not in (ROLE_GENERALIST, ROLE_SOURCER)
        ]

        agent_responses = await self._run_specialists(
            specialist_role_ids,
            session,
            previous_rounds_summary,
            learning_patterns
        )

        # Step 4: Generalist synthesizes
        generalist = self.agents[ROLE_GENERALIST]
        generalist_response = await generalist.analyze(
            task=session.task,
            context=session.context,
            specialist_responses=agent_responses,
            previous_rounds_summary=previous_rounds_summary,
            learning_patterns=learning_patterns
        )

        # Step 5: Merge CROSS scores (all agents including generalist)
        all_responses = agent_responses + [generalist_response]
        merged_cross = self.consensus_builder.merge_cross_scores(all_responses)

        # Step 6: Build summary of what was deliberated
        generalist_prompt = self._build_generalist_prompt_summary(session, round_num)

        # Step 7: Create round result
        round_result = RoundResult(
            round_number=round_num,
            generalist_prompt=generalist_prompt,
            generalist_response=generalist_response,
            agent_responses=agent_responses,
            merged_cross=merged_cross,
            decision=DecisionResult.CONTINUE,
            decision_reasoning=""
        )

        # Step 8: Evaluate for consensus / dead-end
        decision, reasoning = self.consensus_builder.evaluate_round(
            round_result,
            round_num,
            session
        )
        round_result.decision = decision
        round_result.decision_reasoning = reasoning

        return round_result

    async def _run_specialists(
        self,
        role_ids: List[str],
        session: DevSession,
        previous_rounds_summary: List[dict],
        learning_patterns: List[Dict]
    ) -> List[AgentResponse]:
        """Run specialists in parallel or sequential mode."""
        from ids.config import settings

        if not role_ids:
            logger.info("no_specialists_configured")
            return []

        # Delay before first specialist API call
        await asyncio.sleep(settings.agent_delay_seconds)

        if settings.parallel_agents:
            logger.info("executing_specialists_parallel", count=len(role_ids))
            return await self._execute_parallel(role_ids, session, previous_rounds_summary, learning_patterns)
        else:
            logger.info("executing_specialists_sequential", count=len(role_ids))
            return await self._execute_sequential(role_ids, session, previous_rounds_summary, learning_patterns)

    async def _execute_parallel(
        self,
        role_ids: List[str],
        session: DevSession,
        previous_rounds_summary: List[dict],
        learning_patterns: List[Dict]
    ) -> List[AgentResponse]:
        """Execute all specialists in parallel."""
        tasks = [
            self.agents[role_id].analyze(
                task=session.task,
                context=session.context,
                previous_rounds_summary=previous_rounds_summary,
                learning_patterns=learning_patterns
            )
            for role_id in role_ids
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error("specialist_analysis_failed", role_id=role_ids[i], error=str(response))
            else:
                valid_responses.append(response)

        return valid_responses

    async def _execute_sequential(
        self,
        role_ids: List[str],
        session: DevSession,
        previous_rounds_summary: List[dict],
        learning_patterns: List[Dict]
    ) -> List[AgentResponse]:
        """Execute specialists one by one."""
        from ids.config import settings

        responses = []

        for i, role_id in enumerate(role_ids, 1):
            try:
                logger.info("executing_specialist", role_id=role_id, progress=f"{i}/{len(role_ids)}")

                agent = self.agents[role_id]
                response = await agent.analyze(
                    task=session.task,
                    context=session.context,
                    previous_rounds_summary=previous_rounds_summary,
                    learning_patterns=learning_patterns
                )

                responses.append(response)
                logger.info("specialist_complete", role_id=role_id, confidence=response.cross_score.confidence)

                # Delay between calls (except after last)
                if i < len(role_ids):
                    await asyncio.sleep(settings.agent_delay_seconds)

            except Exception as e:
                logger.error("specialist_analysis_failed", role_id=role_id, error=str(e))

        return responses

    def _prepare_round_history(self, session: DevSession) -> List[dict]:
        """Prepare previous rounds data for agents."""
        history = []

        for round_result in session.rounds:
            round_data = {
                "round_number": round_result.round_number,
                "merged_cross": {
                    "avg_confidence": round_result.merged_cross.avg_confidence,
                    "max_risk": round_result.merged_cross.max_risk,
                    "avg_outcome": round_result.merged_cross.avg_outcome
                },
                "agent_responses": [
                    {
                        "agent_id": resp.agent_id,
                        "role_name": resp.role_name,
                        "response": resp.response
                    }
                    for resp in round_result.agent_responses + [round_result.generalist_response]
                ]
            }
            history.append(round_data)

        return history

    def _build_generalist_prompt_summary(self, session: DevSession, round_num: int) -> str:
        """Build a summary of what was asked in this round."""
        parts = [f"Round {round_num} Analysis Request:"]
        parts.append(f"Task: {session.task}")

        if session.context:
            parts.append(f"Context: {session.context}")

        if len(session.rounds) > 0:
            parts.append(f"Previous rounds: {len(session.rounds)}")
            parts.append("Building on previous deliberation to reach consensus.")
        else:
            parts.append("Initial analysis of this task.")

        return "\n".join(parts)
