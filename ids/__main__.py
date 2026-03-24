"""Main entry point for IDS application.

Supports multiple interface transports via ``--interface``:
  - ``telegram`` (default) — Telegram bot polling
  - ``cli``               — Interactive terminal REPL
"""

import argparse
import asyncio
import sys

from ids.utils import setup_logging, get_logger
from ids.config import settings

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IDS — Intelligent Deliberation System")
    parser.add_argument(
        "--interface", "-i",
        choices=["telegram", "cli"],
        default="telegram",
        help="Transport interface to use (default: telegram)",
    )
    return parser.parse_args()


async def _init_core():
    """Initialise storage, services, and orchestrator — shared by all interfaces."""
    from ids.services import LLMClient, ClaudeCodeExecutor
    from ids.services.daily_update_service import DailyUpdateService
    from ids.storage import MongoSessionStore, MongoProjectStore, ChromaStore
    from ids.storage.fingerprint_store import FingerprintStore
    from ids.orchestrator import ConsensusBuilder, SessionManager
    from ids.orchestrator.code_workflow import CodeWorkflow

    logger.info("initializing_llm_client")
    llm_client = LLMClient()

    logger.info("initializing_storage")
    session_store = MongoSessionStore()
    project_store = MongoProjectStore()
    chroma_store = ChromaStore()
    await chroma_store.initialize()

    logger.info("initializing_orchestrator")
    consensus_builder = ConsensusBuilder()
    session_manager = SessionManager(
        llm_client=llm_client,
        consensus_builder=consensus_builder,
        session_store=session_store,
        project_store=project_store,
        chroma_store=chroma_store,
    )

    logger.info("initializing_claude_code")
    claude_executor = ClaudeCodeExecutor()
    code_workflow = CodeWorkflow(claude_executor=claude_executor)

    logger.info("initializing_daily_update_service")
    fingerprint_store = FingerprintStore(chroma_store)
    await fingerprint_store.ensure_indexes()
    daily_update_service = DailyUpdateService(llm_client, fingerprint_store)

    return session_manager, project_store, code_workflow, daily_update_service


async def _run_telegram(session_manager, project_store, code_workflow, daily_update_service):
    """Start IDS with the Telegram interface (backward-compatible path)."""
    from ids.interfaces.telegram import create_bot

    if not settings.telegram_bot_token:
        logger.error("telegram_bot_token_missing")
        print("ERROR: TELEGRAM_BOT_TOKEN is required for the Telegram interface.", file=sys.stderr)
        sys.exit(1)

    logger.info("initializing_telegram_bot")
    app = create_bot(session_manager, project_store, code_workflow, daily_update_service)

    logger.info(
        "ids_ready",
        interface="telegram",
        allowed_users=len(settings.get_allowed_users()),
        max_rounds=settings.max_rounds,
        round_logging=settings.round_logging,
        agent_execution_mode="parallel" if settings.parallel_agents else "sequential",
        agent_delay_seconds=settings.agent_delay_seconds,
        parliament="dynamic_per_project",
    )

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("telegram_bot_running")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("shutdown_signal_received")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def _run_cli(session_manager, project_store, code_workflow, daily_update_service):
    """Start IDS with the interactive CLI interface."""
    from ids.interfaces.cli import CLIAdapter
    from ids.interfaces.command_handler import CommandHandler

    adapter = CLIAdapter()
    handler = CommandHandler(
        session_manager=session_manager,
        project_store=project_store,
        adapter=adapter,
        code_workflow=code_workflow,
        daily_update_service=daily_update_service,
    )
    adapter.set_handler(handler)

    logger.info("ids_ready", interface="cli")

    try:
        await adapter.start()
    except KeyboardInterrupt:
        logger.info("shutdown_signal_received")
    finally:
        await adapter.stop()


async def main():
    """Initialize and start IDS application."""
    args = _parse_args()

    setup_logging()
    logger.info("ids_starting", version="0.3.0", interface=args.interface)

    try:
        core = await _init_core()

        if args.interface == "cli":
            await _run_cli(*core)
        else:
            await _run_telegram(*core)

    except Exception as e:
        logger.error("startup_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
