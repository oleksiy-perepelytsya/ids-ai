"""Agent system - unified agent implementation"""

from .base_agent import Agent
from ids.models import AgentRole
from ids.services import LLMClient


def create_agent(role: AgentRole, llm_client: LLMClient) -> Agent:
    """
    Factory function to create agents.
    All agents use the same Agent class with different personas.
    """
    return Agent(role=role, llm_client=llm_client)


def create_all_agents(llm_client: LLMClient) -> dict:
    """
    Create all agents for Parliament based on settings.
    Only creates agents that are enabled in configuration.
    
    Returns:
        Dict mapping role to agent instance
    """
    from ids.config import settings
    
    agents = {}
    
    # Always create Generalist and Sourcer (required)
    agents[AgentRole.GENERALIST] = create_agent(AgentRole.GENERALIST, llm_client)
    agents[AgentRole.SOURCER] = create_agent(AgentRole.SOURCER, llm_client)
    
    # Create only enabled specialized agents
    enabled_roles = settings.get_enabled_agents()
    
    for role in enabled_roles:
        agents[role] = create_agent(role, llm_client)
    
    return agents


__all__ = ["Agent", "create_agent", "create_all_agents"]
