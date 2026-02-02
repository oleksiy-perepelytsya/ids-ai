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
        consensus_builder: ConsensusBuilder
    ):
        self.agents = agents
        self.consensus_builder = consensus_builder
        logger.info("round_executor_initialized", agent_count=len(agents))
    
    async def execute_round(
        self,
        session: DevSession,
        round_num: int
    ) -> RoundResult:
        """
        Execute a complete deliberation round.
        
        Steps:
        1. Generalist provides initial analysis
        2. All 6 specialized agents analyze in parallel
        3. Merge CROSS scores
        4. Determine decision (consensus/continue/dead-end)
        
        Args:
            session: Current session
            round_num: Round number (1-indexed)
            
        Returns:
            RoundResult with all agent responses and decision
        """
        logger.info("round_started", session_id=session.session_id, round_num=round_num)
        
        # Step 1: Get Generalist analysis
        generalist = self.agents[AgentRole.GENERALIST]
        generalist_response = await self._get_generalist_analysis(
            generalist, 
            session, 
            round_num
        )
        generalist_cross = generalist_response.cross_score
        
        logger.info(
            "generalist_analysis_complete",
            confidence=generalist_cross.confidence,
            risk=generalist_cross.risk,
            outcome=generalist_cross.outcome
        )
        
        # Step 2: Get all specialized agent responses in parallel
        agent_responses = await self._get_specialized_responses(
            session,
            round_num,
            generalist_cross
        )
        
        logger.info(
            "specialized_agents_complete",
            agent_count=len(agent_responses)
        )
        
        # Step 3: Merge CROSS scores
        merged_cross = self.consensus_builder.merge_cross_scores(
            generalist_cross,
            agent_responses
        )
        
        # Step 4: Create round result
        round_result = RoundResult(
            round_number=round_num,
            generalist_cross=generalist_cross,
            agent_responses=agent_responses,
            merged_cross=merged_cross,
            decision=DecisionResult.CONTINUE  # Will be determined by consensus builder
        )
        
        # Step 5: Evaluate and determine decision
        decision = self.consensus_builder.evaluate_round(
            round_result,
            round_num,
            session
        )
        round_result.decision = decision
        
        logger.info(
            "round_complete",
            round_num=round_num,
            decision=decision,
            avg_confidence=merged_cross.avg_confidence,
            max_risk=merged_cross.max_risk
        )
        
        return round_result
    
    async def _get_generalist_analysis(
        self,
        generalist: Agent,
        session: DevSession,
        round_num: int
    ) -> AgentResponse:
        """Get Generalist's initial analysis"""
        # Prepare previous rounds data
        previous_rounds = self._prepare_round_history(session)
        
        # Generalist analyzes without another agent's CROSS
        response = await generalist.analyze(
            task=session.task,
            context=session.context,
            previous_rounds=previous_rounds,
            generalist_cross=None
        )
        
        return response
    
    async def _get_specialized_responses(
        self,
        session: DevSession,
        round_num: int,
        generalist_cross: CrossScore
    ) -> List[AgentResponse]:
        """Get responses from all specialized agents in parallel"""
        
        specialized_roles = [
            AgentRole.DEVELOPER_PROGRESSIVE,
            AgentRole.DEVELOPER_CRITIC,
            AgentRole.ARCHITECT_PROGRESSIVE,
            AgentRole.ARCHITECT_CRITIC,
            AgentRole.SRE_PROGRESSIVE,
            AgentRole.SRE_CRITIC,
        ]
        
        # Prepare previous rounds data
        previous_rounds = self._prepare_round_history(session)
        
        # Create tasks for all agents
        tasks = []
        for role in specialized_roles:
            agent = self.agents[role]
            task = agent.analyze(
                task=session.task,
                context=session.context,
                previous_rounds=previous_rounds,
                generalist_cross=generalist_cross
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
                    role=specialized_roles[i],
                    error=str(response)
                )
            else:
                valid_responses.append(response)
        
        return valid_responses
    
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
