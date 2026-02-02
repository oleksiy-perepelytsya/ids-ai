"""Session manager - manages complete deliberation sessions"""

import uuid
from datetime import datetime
from typing import Optional, Callable, Awaitable
from ids.models import (
    DevSession,
    SessionStatus,
    DecisionResult,
    RoundResult
)
from ids.storage import MongoSessionStore, MongoProjectStore
from ids.orchestrator.round_executor import RoundExecutor
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Manages complete deliberation sessions.
    Coordinates round execution, user feedback, and persistence.
    """
    
    def __init__(
        self,
        round_executor: RoundExecutor,
        session_store: MongoSessionStore,
        project_store: MongoProjectStore
    ):
        self.round_executor = round_executor
        self.session_store = session_store
        self.project_store = project_store
        logger.info("session_manager_initialized")
    
    async def create_session(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        task: str,
        project_name: Optional[str] = None
    ) -> DevSession:
        """
        Create a new deliberation session.
        
        Args:
            telegram_user_id: User's Telegram ID
            telegram_chat_id: Chat ID for responses
            task: The question/task to deliberate on
            project_name: Optional project context
            
        Returns:
            Created DevSession
        """
        session_id = f"sess_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        session = DevSession(
            session_id=session_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            task=task,
            project_name=project_name,
            status=SessionStatus.PENDING
        )
        
        # Save to storage
        await self.session_store.create_session(session)
        
        logger.info(
            "session_created",
            session_id=session_id,
            user_id=telegram_user_id,
            project=project_name
        )
        
        return session
    
    async def run_deliberation(
        self,
        session: DevSession,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> DevSession:
        """
        Run complete multi-round deliberation.
        
        Args:
            session: Session to run deliberation for
            progress_callback: Optional callback for progress updates
            
        Returns:
            Updated session with results
        """
        session.status = SessionStatus.DELIBERATING
        await self.session_store.update_session(session)
        
        logger.info("deliberation_started", session_id=session.session_id)
        
        max_rounds = settings.max_rounds
        
        for round_num in range(1, max_rounds + 1):
            # Send progress update
            if progress_callback:
                await progress_callback(f"⏳ Round {round_num} in progress...")
            
            # Execute round
            round_result = await self.round_executor.execute_round(session, round_num)
            
            # Add to session
            session.add_round(round_result)
            await self.session_store.update_session(session)
            
            # Send round result update (if logging enabled)
            if settings.round_logging and progress_callback:
                update_msg = self._format_round_update(round_result)
                await progress_callback(update_msg)
            
            # Check decision
            if round_result.decision == DecisionResult.CONSENSUS:
                session.status = SessionStatus.CONSENSUS
                await self.session_store.update_session(session)
                
                logger.info(
                    "consensus_reached",
                    session_id=session.session_id,
                    round_num=round_num
                )
                
                if progress_callback:
                    await progress_callback("✅ Consensus reached!")
                
                return session
            
            elif round_result.decision == DecisionResult.DEAD_END:
                session.status = SessionStatus.DEAD_END
                await self.session_store.update_session(session)
                
                logger.info(
                    "dead_end_reached",
                    session_id=session.session_id,
                    round_num=round_num
                )
                
                if progress_callback:
                    await progress_callback("⚠️ Dead-end reached. Need your guidance...")
                
                return session
            
            # Continue to next round
            if progress_callback:
                await progress_callback(f"Continuing to Round {round_num + 1}...")
        
        # Max rounds reached without consensus
        session.status = SessionStatus.DEAD_END
        await self.session_store.update_session(session)
        
        logger.info(
            "max_rounds_reached",
            session_id=session.session_id,
            rounds=max_rounds
        )
        
        if progress_callback:
            await progress_callback(
                f"⚠️ Reached maximum rounds ({max_rounds}). Need your guidance..."
            )
        
        return session
    
    async def handle_user_feedback(
        self,
        session_id: str,
        feedback: str,
        restart: bool = False
    ) -> DevSession:
        """
        Handle user feedback after dead-end.
        
        Args:
            session_id: Session ID
            feedback: User's guidance/feedback
            restart: If True, clear previous rounds and start fresh
            
        Returns:
            Updated session
        """
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        if restart:
            # Clear previous deliberation
            session.rounds = []
            session.context = feedback
            logger.info("session_restarted", session_id=session_id)
        else:
            # Add feedback to context
            session.context += f"\n\nUser guidance: {feedback}"
            logger.info("user_feedback_added", session_id=session_id)
        
        # Reset status
        session.status = SessionStatus.DELIBERATING
        await self.session_store.update_session(session)
        
        return session
    
    async def continue_session(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> DevSession:
        """
        Continue a session after user feedback.
        
        Args:
            session_id: Session ID to continue
            progress_callback: Optional callback for updates
            
        Returns:
            Updated session
        """
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        logger.info("continuing_session", session_id=session_id)
        
        # Continue deliberation
        return await self.run_deliberation(session, progress_callback)
    
    async def cancel_session(self, session_id: str) -> DevSession:
        """
        Cancel a session.
        
        Args:
            session_id: Session ID to cancel
            
        Returns:
            Updated session
        """
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.status = SessionStatus.CANCELLED
        await self.session_store.update_session(session)
        
        logger.info("session_cancelled", session_id=session_id)
        
        return session
    
    def _format_round_update(self, round_result: RoundResult) -> str:
        """Format round result for Telegram display"""
        merged = round_result.merged_cross
        
        # Agreement indicator
        if merged.std_confidence < 10:
            agreement = "🎯 High"
        elif merged.std_confidence < 20:
            agreement = "👍 Good"
        else:
            agreement = "⚠️ Divergent"
        
        msg = (
            f"📊 Round {round_result.round_number} Results:\n\n"
            f"Confidence: {merged.avg_confidence:.1f}%\n"
            f"Risk: {merged.max_risk:.1f}%\n"
            f"Outcome: {merged.avg_outcome:.1f}%\n"
            f"Agreement: {agreement}\n"
        )
        
        return msg
