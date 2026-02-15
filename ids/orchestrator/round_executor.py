"""Round executor - executes a single deliberation round"""

import asyncio
from typing import List
from ids.models import AgentRole, AgentResponse, CrossScore, RoundResult, DecisionResult, DevSession
from ids.agents import Agent
from ids.orchestrator.consensus_builder import ConsensusBuilder
from ids.utils import get_logger

logger = get_logger(__name__)


class RoundExecutor:
    """Executes a single deliberation round with all agents"""
    
    def __init__(
        self,
        agents: dict,  # Dict[AgentRole, Agent]
        consensus_builder: ConsensusBuilder,
        chroma_store: Optional[any] = None
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
        
        New Flow:
        Round 1: 
          1. Retrieval: Get learning patterns from ChromaDB
          2. Specialists analyze task directly (with RAG context)
          3. Generalist summarize specialists and provides CROSS score
        
        Round 2+:
          1. Generalist instigates based on previous rounds
          2. Specialists analyze based on Generalist's direction
        """
        logger.info("round_started", session_id=session.session_id, round_num=round_num)
        
        # Step 0: Retrieval (RAG)
        learning_patterns = []
        if self.chroma_store and session.project_name:
            # We use project_name or project_id if available. 
            # Assuming project_name mapped correctly or we can use it.
            # Usually we use project_id, let's check session model.
            # Looks like session has project_name.
            learning_patterns = await self.chroma_store.search_learning_patterns(
                project_id=session.project_name, 
                query=session.task
            )
            logger.info("rag_context_retrieved", count=len(learning_patterns))

        if round_num == 1:
            # Step 1: Specialized agents analyze first
            agent_responses = await self._get_specialized_responses(
                session,
                round_num,
                generalist_cross=None,
                learning_patterns=learning_patterns
            )
            
            # Step 2: Generalist summarizes specialists
            generalist = self.agents[AgentRole.GENERALIST]
            
            # Build a special context for the generalist in Round 1
            specialists_summary = "\n".join([
                f"- {r.agent_id}: {r.proposed_approach}" for r in agent_responses
            ])
            round1_context = (
                f"{session.context}\n\n"
                f"SPECIALISTS INITIAL PERSPECTIVES:\n{specialists_summary}"
            )
            
            generalist_response = await generalist.analyze(
                task=session.task,
                context=round1_context,
                previous_rounds=[],
                generalist_cross=None,
                learning_patterns=learning_patterns
            )
        else:
            # Round 2+: Generalist instigates first
            generalist = self.agents[AgentRole.GENERALIST]
            generalist_response = await self._get_generalist_analysis(
                generalist, 
                session, 
                round_num,
                learning_patterns=learning_patterns
            )
            
            # Then specialized agents respond
            agent_responses = await self._get_specialized_responses(
                session,
                round_num,
                generalist_cross=generalist_response.cross_score,
                learning_patterns=learning_patterns
            )
        
        generalist_cross = generalist_response.cross_score
        
        # Step 3: Merge CROSS scores
        merged_cross = self.consensus_builder.merge_cross_scores(
            generalist_cross,
            agent_responses
        )
        
        # Step 4: Build the generalist prompt that was used
        generalist_prompt = self._build_generalist_prompt_summary(session, round_num)
        
        # Step 5: Create round result
        round_result = RoundResult(
            round_number=round_num,
            generalist_prompt=generalist_prompt,
            generalist_response=generalist_response,
            generalist_cross=generalist_cross,
            agent_responses=agent_responses,
            merged_cross=merged_cross,
            decision=DecisionResult.CONTINUE,
            decision_reasoning=""
        )
        
        # Step 6: Evaluate
        decision, reasoning = self.consensus_builder.evaluate_round(
            round_result,
            round_num,
            session
        )
        round_result.decision = decision
        round_result.decision_reasoning = reasoning
        
        return round_result
    
    async def _get_generalist_analysis(
        self,
        generalist: Agent,
        session: DevSession,
        round_num: int,
        learning_patterns: Optional[List[Dict]] = None
    ) -> AgentResponse:
        """Get Generalist's initial analysis"""
        # Prepare previous rounds data
        previous_rounds = self._prepare_round_history(session)
        
        # Generalist analyzes without another agent's CROSS
        response = await generalist.analyze(
            task=session.task,
            context=session.context,
            previous_rounds=previous_rounds,
            generalist_cross=None,
            learning_patterns=learning_patterns
        )
        
        return response
    
    async def _get_specialized_responses(
        self,
        session: DevSession,
        round_num: int,
        generalist_cross: Optional[CrossScore] = None,
        learning_patterns: Optional[List[Dict]] = None
    ) -> List[AgentResponse]:
        """Get responses from all specialized agents in parallel or sequential"""
        
        specialized_roles = [
            role for role in [
                AgentRole.DEVELOPER_PROGRESSIVE,
                AgentRole.DEVELOPER_CRITIC,
                AgentRole.ARCHITECT_PROGRESSIVE,
                AgentRole.ARCHITECT_CRITIC,
                AgentRole.SRE_PROGRESSIVE,
                AgentRole.SRE_CRITIC,
            ] if role in self.agents
        ]
        
        # Prepare previous rounds data
        previous_rounds = self._prepare_round_history(session)
        
        # Import settings to check execution mode
        from ids.config import settings
        
        # Delay after Generalist before first specialized agent (both hit APIs)
        await asyncio.sleep(settings.agent_delay_seconds)
        
        if settings.parallel_agents:
            # PARALLEL MODE (requires higher API quota)
            logger.info("executing_agents_parallel", count=len(specialized_roles))
            return await self._execute_parallel(
                specialized_roles, 
                session, 
                previous_rounds, 
                generalist_cross,
                learning_patterns
            )
        else:
            # SEQUENTIAL MODE (avoids rate limits)
            logger.info("executing_agents_sequential", count=len(specialized_roles))
            return await self._execute_sequential(
                specialized_roles,
                session,
                previous_rounds,
                generalist_cross,
                learning_patterns
            )
    
    async def _execute_parallel(
        self,
        roles: List[AgentRole],
        session: DevSession,
        previous_rounds: List[dict],
        generalist_cross: Optional[CrossScore] = None,
        learning_patterns: Optional[List[Dict]] = None
    ) -> List[AgentResponse]:
        """Execute all agents in parallel (fast but needs high quota)"""
        
        # Create tasks for all agents
        tasks = []
        for role in roles:
            agent = self.agents[role]
            task = agent.analyze(
                task=session.task,
                context=session.context,
                previous_rounds=previous_rounds,
                generalist_cross=generalist_cross,
                learning_patterns=learning_patterns
            )
            tasks.append(task)
        
        # Execute all in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any errors and log them
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(
                    "agent_analysis_failed",
                    role=roles[i],
                    error=str(response)
                )
            else:
                valid_responses.append(response)
        
        return valid_responses
    
    async def _execute_sequential(
        self,
        roles: List[AgentRole],
        session: DevSession,
        previous_rounds: List[dict],
        generalist_cross: Optional[CrossScore] = None,
        learning_patterns: Optional[List[Dict]] = None
    ) -> List[AgentResponse]:
        """Execute agents one by one (slower but avoids rate limits)"""
        from ids.config import settings
        
        responses = []
        
        for i, role in enumerate(roles, 1):
            try:
                logger.info(
                    "executing_agent",
                    role=role,
                    progress=f"{i}/{len(roles)}"
                )
                
                agent = self.agents[role]
                response = await agent.analyze(
                    task=session.task,
                    context=session.context,
                    previous_rounds=previous_rounds,
                    generalist_cross=generalist_cross,
                    learning_patterns=learning_patterns
                )
                
                responses.append(response)
                
                logger.info(
                    "agent_complete",
                    role=role,
                    confidence=response.cross_score.confidence
                )
                
                # Delay between calls to avoid rate limits (except after last agent)
                if i < len(roles):
                    delay = settings.agent_delay_seconds
                    logger.debug("rate_limit_delay", seconds=delay)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(
                    "agent_analysis_failed",
                    role=role,
                    error=str(e)
                )
                # Continue with other agents even if one fails
        
        return responses
    
    def _prepare_round_history(self, session: DevSession) -> List[dict]:
        """Prepare previous rounds data for agents"""
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
                        "proposed_approach": resp.proposed_approach,
                        "concerns": resp.concerns
                    }
                    for resp in round_result.agent_responses
                ]
            }
            history.append(round_data)
        
        return history

    def _build_generalist_prompt_summary(self, session: DevSession, round_num: int) -> str:
        """Build a summary of what was asked in this round"""
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

