"""Session manager - manages complete deliberation sessions"""

import uuid
from datetime import datetime
from typing import Optional, Callable, Awaitable
from ids.models import (
    DevSession,
    SessionStatus,
    DecisionResult,
    ROLE_SOURCER,
    SourcerLog,
)
from ids.storage import MongoSessionStore, MongoProjectStore, ChromaStore
from ids.orchestrator.round_executor import RoundExecutor
from ids.orchestrator.consensus_builder import ConsensusBuilder
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
        llm_client,
        consensus_builder: ConsensusBuilder,
        session_store: MongoSessionStore,
        project_store: MongoProjectStore,
        chroma_store: Optional[ChromaStore] = None
    ):
        self.llm_client = llm_client
        self.consensus_builder = consensus_builder
        self.session_store = session_store
        self.project_store = project_store
        self.chroma_store = chroma_store
        # Agent cache: project_id -> dict of agents
        self._agent_cache: dict[str, dict] = {}
        logger.info("session_manager_initialized")

    async def _get_agents(self, project_id: str) -> dict:
        """Load and cache agents for a project."""
        if project_id in self._agent_cache:
            return self._agent_cache[project_id]

        from ids.agents import create_agents_for_project

        project = await self.project_store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        agents = await create_agents_for_project(project, self.llm_client)
        self._agent_cache[project_id] = agents
        logger.info("agent_cache_populated", project_id=project_id, agent_count=len(agents))
        return agents

    async def _get_executor(self, project_id: str) -> RoundExecutor:
        """Get a RoundExecutor for the given project (uses cached agents)."""
        agents = await self._get_agents(project_id)
        project = await self.project_store.get_project(project_id)
        embedding_model = project.embedding_model if project else "default"
        return RoundExecutor(agents, self.consensus_builder, self.chroma_store, embedding_model=embedding_model)

    def invalidate_agent_cache(self, project_id: str) -> None:
        """Remove cached agents for a project (call after prompt URL changes)."""
        if project_id in self._agent_cache:
            del self._agent_cache[project_id]
            logger.info("agent_cache_invalidated", project_id=project_id)

    async def create_session(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        task: str,
        project_id: str,
        project_name: Optional[str] = None
    ) -> DevSession:
        """
        Create a new deliberation session.

        Args:
            telegram_user_id: User's Telegram ID
            telegram_chat_id: Chat ID for responses
            task: The question/task to deliberate on
            project_id: Required project identifier
            project_name: Display name for the project

        Returns:
            Created DevSession
        """
        session_id = f"sess_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        session = DevSession(
            session_id=session_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            task=task,
            project_id=project_id,
            project_name=project_name,
            status=SessionStatus.PENDING
        )

        # Save to storage
        await self.session_store.create_session(session)

        logger.info(
            "session_created",
            session_id=session_id,
            user_id=telegram_user_id,
            project_id=project_id
        )

        return session

    async def run_deliberation(
        self,
        session: DevSession,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> DevSession:
        """
        Run a single deliberation round.

        Args:
            session: Session to run deliberation for
            progress_callback: Optional callback for progress updates

        Returns:
            Updated session with results
        """
        session.status = SessionStatus.DELIBERATING
        await self.session_store.update_session(session)

        logger.info("deliberation_started", session_id=session.session_id)

        round_num = session.get_current_round_number()

        # Check if we've already reached max rounds (project override or global default)
        project = await self.project_store.get_project(session.project_id)
        max_rounds = (project.max_rounds if project and project.max_rounds else None) or settings.max_rounds
        if round_num > max_rounds:
            session.status = SessionStatus.DEAD_END
            await self.session_store.update_session(session)
            if progress_callback:
                await progress_callback(
                    f"⚠️ Reached maximum rounds ({max_rounds}). Need your guidance..."
                )
            return session

        # Send progress update
        if progress_callback:
            await progress_callback(f"⏳ Round {round_num} in progress...")

        # Get executor for this project
        executor = await self._get_executor(session.project_id)

        # Execute round
        round_result = await executor.execute_round(session, round_num, max_rounds=max_rounds)

        # Add to session
        session.add_round(round_result)

        # Update status based on decision
        if round_result.decision == DecisionResult.CONSENSUS:
            session.status = SessionStatus.CONSENSUS
            logger.info("consensus_reached", session_id=session.session_id, round_num=round_num)
            if progress_callback:
                await progress_callback("✅ Consensus reached!")
        elif round_result.decision == DecisionResult.DEAD_END:
            session.status = SessionStatus.DEAD_END
            logger.info("dead_end_reached", session_id=session.session_id, round_num=round_num)
            if progress_callback:
                await progress_callback("⚠️ Dead-end reached. Need your guidance...")
        else:
            # Continue to next round but pause for user input
            session.status = SessionStatus.AWAITING_CONTINUATION
            logger.info("awaiting_continuation", session_id=session.session_id, next_round=round_num + 1)

        await self.session_store.update_session(session)
        return session

    async def handle_user_feedback(
        self,
        session_id: str,
        feedback: str,
        restart: bool = False
    ) -> DevSession:
        """Handle user feedback after dead-end."""
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if restart:
            session.rounds = []
            session.context = feedback
            logger.info("session_restarted", session_id=session_id)
        else:
            session.context += f"\n\nUser guidance: {feedback}"
            logger.info("user_feedback_added", session_id=session_id)

        session.status = SessionStatus.DELIBERATING
        await self.session_store.update_session(session)

        return session

    async def continue_session(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> DevSession:
        """Continue a session after user feedback."""
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        logger.info("continuing_session", session_id=session_id)
        return await self.run_deliberation(session, progress_callback)

    async def cancel_session(self, session_id: str) -> DevSession:
        """Cancel a session."""
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.status = SessionStatus.CANCELLED
        await self.session_store.update_session(session)

        logger.info("session_cancelled", session_id=session_id)
        return session

    async def delete_project(self, project_id: str) -> dict:
        """
        Delete a project and all its data from every store.
        Returns a summary of what was deleted.
        """
        self.invalidate_agent_cache(project_id)

        sessions_deleted = await self.session_store.delete_project_sessions(project_id)
        project_deleted = await self.project_store.delete_project(project_id)

        if self.chroma_store:
            await self.chroma_store.delete_project_data(project_id)

        logger.info(
            "project_fully_deleted",
            project_id=project_id,
            sessions_deleted=sessions_deleted,
        )
        return {"sessions_deleted": sessions_deleted, "project_deleted": project_deleted}

    async def learn_from_text(self, project_id: str, text: str, embedding_model: str = "default") -> None:
        """Directly store text as learning data in ChromaDB"""
        if self.chroma_store:
            await self.chroma_store.add_learning_pattern(
                project_id=project_id,
                content=text,
                metadata={"type": "direct_learning", "timestamp": datetime.utcnow().isoformat()},
                embedding_model=embedding_model,
            )
            logger.info("direct_learning_added", project_id=project_id)

    async def embed_file_chunks(
        self, project_id: str, filename: str, chunks: list[str], embedding_model: str = "default"
    ) -> int:
        """Store file text chunks as learning patterns in ChromaDB. Returns number of chunks stored."""
        if not self.chroma_store:
            return 0

        stored = 0
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            metadata = {
                "type": "file_upload",
                "filename": filename,
                "chunk_index": i,
                "total_chunks": total,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.chroma_store.add_learning_pattern(
                project_id=project_id,
                content=chunk,
                metadata=metadata,
                embedding_model=embedding_model,
            )
            stored += 1

        logger.info("file_embedded", project_id=project_id, filename=filename, chunks=stored)
        return stored

    async def run_sourcer(
        self,
        project_id: str,
        task: str,
        model: str,
        embedding_model: str = "default",
        genprompt_model: Optional[str] = None,
        telegram_user_id: int = 0,
    ) -> tuple[str, Optional[str]]:
        """
        Run single-agent 'Sourcer' mode with RAG from ChromaDB + MongoDB session history.

        If genprompt_model is set, first calls that model to generate an optimised
        search prompt, then uses the generated prompt for the actual sourcer call.

        Returns:
            (response_text, generated_prompt_or_None)
        """
        agents = await self._get_agents(project_id)
        sourcer = agents.get(ROLE_SOURCER)
        if not sourcer:
            raise ValueError("Sourcer agent not initialized for this project")

        # Step 1 (optional): generate an optimised prompt
        generated_prompt: Optional[str] = None
        search_query = task
        if genprompt_model:
            project = await self.project_store.get_project(project_id)
            genprompt_system = "You are a search-query optimisation expert. Given a user question and a knowledge base context, rewrite the question into a precise, comprehensive search query that will retrieve the most relevant information. Return only the improved query — no explanation."
            if project and project.genprompt_prompt_url:
                from ids.services.prompt_loader import fetch_or_fallback
                genprompt_system = await fetch_or_fallback(project.genprompt_prompt_url, None) or genprompt_system
            generated_prompt = await self.llm_client.call_model(
                model=genprompt_model,
                prompt=f"Original question:\n{task}\n\nGenerate an optimised search query for a scientific knowledge base.",
                system_prompt=genprompt_system,
                max_tokens=2000,
            )
            search_query = generated_prompt.strip()
            logger.info("genprompt_generated", project_id=project_id, model=genprompt_model, length=len(search_query))

        # Step 2: RAG retrieval using (generated or original) query
        learning_patterns = []
        if self.chroma_store:
            learning_patterns = await self.chroma_store.search_learning_patterns(
                project_id=project_id,
                query=search_query,
                embedding_model=embedding_model,
            )

        # MongoDB: recent consensus session history
        past_sessions = await self.session_store.get_completed_sessions(project_id)
        for session in past_sessions:
            if not session.rounds:
                continue
            last_round = session.rounds[-1]
            summary = (
                f"Past deliberation: {session.task}\n"
                f"Conclusion: {last_round.generalist_response.response}"
            )
            learning_patterns.append({
                "content": summary,
                "metadata": {"type": "past_session", "session_id": session.session_id}
            })

        logger.info(
            "sourcer_context_built",
            project_id=project_id,
            chroma_patterns=len(learning_patterns) - len(past_sessions),
            mongo_sessions=len(past_sessions)
        )

        # Step 3: Sourcer analysis
        response = await sourcer.analyze(
            task=search_query,
            learning_patterns=learning_patterns,
            model_override=model
        )

        # Step 4: Persist log
        log = SourcerLog(
            log_id=f"src_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            telegram_user_id=telegram_user_id,
            original_query=task,
            generated_prompt=generated_prompt,
            genprompt_model=genprompt_model,
            search_query=search_query,
            sourcer_model=model,
            response=response.response,
        )
        await self.session_store.save_sourcer_log(log)

        return response.response, generated_prompt
