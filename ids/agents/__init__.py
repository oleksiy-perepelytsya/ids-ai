"""Agent system - dynamic parliament construction from project prompt URLs"""

from .base_agent import Agent
from ids.models import Project, ROLE_GENERALIST, ROLE_SOURCER
from ids.services import LLMClient
from ids.services.prompt_loader import fetch_or_fallback
from ids.utils import get_logger

logger = get_logger(__name__)


async def create_agents_for_project(project: Project, llm_client: LLMClient) -> dict:
    """
    Create all agents for a project's parliament based on its prompt URLs.

    - Generalist (Claude): fetched from project.generalist_prompt_url or fallback 'generalist.md'
    - Sourcer (Gemini): fetched from project.sourcer_prompt_url or fallback 'sourcer.md'
    - Specialists (Gemini): one per entry in project.specialist_prompt_urls, sorted by key

    Returns:
        Dict mapping role_id -> Agent
    """
    agents: dict[str, Agent] = {}

    # Generalist (Claude)
    generalist_prompt = await fetch_or_fallback(project.generalist_prompt_url, "generalist.md")
    agents[ROLE_GENERALIST] = Agent(
        role_id=ROLE_GENERALIST,
        system_prompt=generalist_prompt,
        llm_client=llm_client,
        max_tokens=project.generalist_max_tokens
    )

    # Sourcer (Gemini)
    sourcer_prompt = await fetch_or_fallback(project.sourcer_prompt_url, "sourcer.md")
    agents[ROLE_SOURCER] = Agent(
        role_id=ROLE_SOURCER,
        system_prompt=sourcer_prompt,
        llm_client=llm_client,
        max_tokens=project.sourcer_max_tokens
    )

    # Specialists (Gemini) — sorted numerically by key
    specialist_keys = sorted(project.specialist_prompt_urls.keys(), key=lambda k: int(k))
    for key in specialist_keys:
        url = project.specialist_prompt_urls[key]
        role_id = f"specialist_{key}"
        specialist_prompt = await fetch_or_fallback(url, "generalist.md")
        agents[role_id] = Agent(
            role_id=role_id,
            system_prompt=specialist_prompt,
            llm_client=llm_client,
            max_tokens=project.specialist_max_tokens
        )

    logger.info(
        "agents_created_for_project",
        project_id=project.project_id,
        specialist_count=len(specialist_keys),
        total_agents=len(agents)
    )

    return agents


__all__ = ["Agent", "create_agents_for_project"]
