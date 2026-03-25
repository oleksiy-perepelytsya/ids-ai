"""Context collectors for the hostess agent.

Each ``collect_*`` function gathers one section of context and returns
a plain-text string (or ``None`` when there is nothing to report).
Adding, removing, or reordering collectors is straightforward — just
edit the ``COLLECTORS`` list at the bottom of the file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ids.config import settings
from ids.utils import get_logger

if TYPE_CHECKING:
    from ids.models import Project
    from ids.storage import ChromaStore, MongoProjectStore, MongoSessionStore

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Individual collectors
# ------------------------------------------------------------------

def collect_project_overview(project: Project) -> Optional[str]:
    """Basic project identity and configuration."""
    sc = len(set(project.specialist_prompt_urls) | set(project.specialist_prompts))
    lines = [
        f"Active project: '{project.name}' "
        f"(id: {project.project_id}, {sc} specialist(s) configured, "
        f"embedding: {project.embedding_model})",
    ]
    if project.description:
        lines.append(f"Project description: {project.description}")
    mr = project.max_rounds or settings.max_rounds
    gm = project.generalist_model or settings.claude_model
    lines.append(
        f"Settings: max_rounds={mr}, generalist_model={gm}, "
        f"specialist_tokens={project.specialist_max_tokens}, "
        f"generalist_tokens={project.generalist_max_tokens}, "
        f"sourcer_tokens={project.sourcer_max_tokens}"
    )
    return "\n".join(lines)


def collect_specialist_roles(project: Project) -> Optional[str]:
    """List of configured specialist slots with role names."""
    all_keys = sorted(
        set(project.specialist_prompt_urls.keys()) | set(project.specialist_prompts.keys()),
        key=int,
    )
    if not all_keys:
        return None
    roles = []
    for key in all_keys:
        rn = project.specialist_role_names.get(key)
        src = "library" if key in project.specialist_prompts else "url"
        roles.append(f"  specialist_{key}: {rn or '(unnamed)'} ({src})")
    return "Configured specialists:\n" + "\n".join(roles)


async def collect_session_stats(
    session_store: MongoSessionStore,
    user_id: int,
    project: Project,
) -> Optional[str]:
    """Session counts broken down by status, plus total rounds."""
    all_sessions = await session_store.get_user_sessions(
        user_id, project.project_id, limit=100,
    )
    if not all_sessions:
        return None

    status_counts: dict[str, int] = {}
    for s in all_sessions:
        status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1
    total_rounds = sum(len(s.rounds) for s in all_sessions)
    last_date = all_sessions[0].created_at.strftime("%Y-%m-%d %H:%M")

    return (
        f"Session statistics (project '{project.name}'):\n"
        f"  Total sessions: {len(all_sessions)}\n"
        f"  By status: {status_counts}\n"
        f"  Total deliberation rounds: {total_rounds}\n"
        f"  Last session: {last_date} — \"{all_sessions[0].task[:80]}\""
    )


async def collect_recent_sessions(
    session_store: MongoSessionStore,
    user_id: int,
    project: Project,
) -> Optional[str]:
    """Short summaries of the last few sessions."""
    recent = await session_store.get_user_sessions(
        user_id, project.project_id, limit=5,
    )
    if not recent:
        return None

    lines = []
    for s in recent:
        lines.append(
            f"  - [{s.status.value}] \"{s.task[:60]}\" "
            f"({len(s.rounds)} rounds, {s.created_at.strftime('%Y-%m-%d')})"
        )
    return "Recent sessions:\n" + "\n".join(lines)


async def collect_sourcer_activity(
    session_store: MongoSessionStore,
    project: Project,
) -> Optional[str]:
    """Recent sourcer invocations."""
    logs = await session_store.get_sourcer_logs(project.project_id, limit=5)
    if not logs:
        return None
    return (
        f"Sourcer activity: {len(logs)} recent queries, "
        f"last: \"{logs[0].original_query[:60]}\" ({logs[0].sourcer_model})"
    )


async def collect_prompt_library(
    session_store: MongoSessionStore,
    project: Project,
) -> Optional[str]:
    """Generated prompts stored in the library."""
    entries = await session_store.list_prompt_library(project.project_id)
    if not entries:
        return None
    names = [f"{e.role_name} ({e.generator_model})" for e in entries]
    return f"Prompt library: {', '.join(names)}"


async def collect_kb_search(
    chroma_store: Optional[ChromaStore],
    project: Project,
    query: str,
) -> Optional[str]:
    """Search the project knowledge base for snippets related to the query."""
    if not chroma_store:
        return None
    try:
        results = await chroma_store.search_learning_patterns(
            project.project_id, query, n_results=3,
            embedding_model=project.embedding_model,
        )
        if not results:
            return None
        lines = []
        for i, r in enumerate(results, 1):
            snippet = r["content"][:200]
            dist = r.get("distance")
            dist_str = f" (distance: {dist:.3f})" if dist is not None else ""
            lines.append(f"  {i}. {snippet}...{dist_str}")
        return "Knowledge base search results for the user's question:\n" + "\n".join(lines)
    except Exception as e:
        logger.debug("hostess_kb_search_failed", error=str(e))
        return None


async def collect_all_projects(
    project_store: MongoProjectStore,
    user_id: int,
) -> Optional[str]:
    """List every project the user owns."""
    projects = await project_store.get_user_projects(user_id)
    if not projects:
        return None
    lines = []
    for p in projects:
        sc = len(set(p.specialist_prompt_urls) | set(p.specialist_prompts))
        lines.append(f"  - {p.name}: {sc} specialist(s), embedding={p.embedding_model}")
    return "All user projects:\n" + "\n".join(lines)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

async def build_hostess_context(
    *,
    user_id: int,
    project: Optional[Project],
    question: str,
    session_store: MongoSessionStore,
    project_store: MongoProjectStore,
    chroma_store: Optional[ChromaStore],
) -> str:
    """Assemble the full context string passed to the hostess LLM.

    Runs every collector in ``COLLECTORS`` order, skipping those that
    return ``None``.  Each collector is a ``(fn, needs_project)`` pair
    so project-less collectors (like ``collect_all_projects``) still run
    when no project is selected.
    """
    parts: list[str] = []

    if project:
        # Synchronous collectors
        for fn in _SYNC_PROJECT_COLLECTORS:
            section = fn(project)
            if section:
                parts.append(section)

        # Async collectors that need a project
        for fn, kwargs in _async_project_collectors(
            session_store=session_store,
            chroma_store=chroma_store,
            user_id=user_id,
            project=project,
            question=question,
        ):
            section = await fn(**kwargs)
            if section:
                parts.append(section)
    else:
        parts.append("User has no active project selected.")

    # Global collectors (always run)
    section = await collect_all_projects(project_store, user_id)
    if section:
        parts.append(section)

    return "\n".join(parts)


# ------------------------------------------------------------------
# Collector registries — edit these to add / remove / reorder
# ------------------------------------------------------------------

_SYNC_PROJECT_COLLECTORS = [
    collect_project_overview,
    collect_specialist_roles,
]


def _async_project_collectors(
    session_store: MongoSessionStore,
    chroma_store: Optional[ChromaStore],
    user_id: int,
    project: Project,
    question: str,
) -> list[tuple]:
    """Return ``(coroutine_fn, kwargs)`` pairs for async project collectors."""
    return [
        (collect_session_stats, dict(
            session_store=session_store, user_id=user_id, project=project,
        )),
        (collect_recent_sessions, dict(
            session_store=session_store, user_id=user_id, project=project,
        )),
        (collect_sourcer_activity, dict(
            session_store=session_store, project=project,
        )),
        (collect_prompt_library, dict(
            session_store=session_store, project=project,
        )),
        (collect_kb_search, dict(
            chroma_store=chroma_store, project=project, query=question,
        )),
    ]
