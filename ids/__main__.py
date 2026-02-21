"""Main entry point for IDS application"""

import asyncio
import sys
from ids.utils import setup_logging, get_logger
from ids.config import settings
from ids.services import LLMClient, ClaudeCodeExecutor
from ids.storage import MongoSessionStore, MongoProjectStore, ChromaStore
from ids.orchestrator import ConsensusBuilder, SessionManager
from ids.orchestrator.code_workflow import CodeWorkflow
from ids.interfaces.telegram import create_bot

logger = get_logger(__name__)


async def main():
    """Initialize and start IDS application"""

    # Setup logging
    setup_logging()
    logger.info("ids_starting", version="0.2.0")

    try:
        # Initialize LLM client
        logger.info("initializing_llm_client")
        llm_client = LLMClient()

        # Initialize storage
        logger.info("initializing_storage")
        session_store = MongoSessionStore()
        project_store = MongoProjectStore()
        chroma_store = ChromaStore()

        # Initialize ChromaDB with async method
        await chroma_store.initialize()

        # Initialize orchestrator
        logger.info("initializing_orchestrator")
        consensus_builder = ConsensusBuilder()
        session_manager = SessionManager(
            llm_client=llm_client,
            consensus_builder=consensus_builder,
            session_store=session_store,
            project_store=project_store,
            chroma_store=chroma_store
        )

        # Initialize Claude Code integration
        logger.info("initializing_claude_code")
        claude_executor = ClaudeCodeExecutor()
        code_workflow = CodeWorkflow(claude_executor=claude_executor)

        # Create Telegram bot
        logger.info("initializing_telegram_bot")
        app = create_bot(session_manager, project_store, code_workflow)

        # Start bot
        logger.info(
            "ids_ready",
            allowed_users=len(settings.get_allowed_users()),
            max_rounds=settings.max_rounds,
            round_logging=settings.round_logging,
            agent_execution_mode="parallel" if settings.parallel_agents else "sequential",
            agent_delay_seconds=settings.agent_delay_seconds,
            parliament="dynamic_per_project"
        )

        # Run polling
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        logger.info("telegram_bot_running")

        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("shutdown_signal_received")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    except Exception as e:
        logger.error("startup_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
