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
    Create all 7 agents for Parliament.
    
    Returns:
        Dict mapping role to agent instance
    """
    agents = {}
    
    # Create Generalist
    agents[AgentRole.GENERALIST] = create_agent(AgentRole.GENERALIST, llm_client)
    
    # Create specialized agents
    specialized_roles = [
        AgentRole.DEVELOPER_PROGRESSIVE,
        AgentRole.DEVELOPER_CRITIC,
        AgentRole.ARCHITECT_PROGRESSIVE,
        AgentRole.ARCHITECT_CRITIC,
        AgentRole.SRE_PROGRESSIVE,
        AgentRole.SRE_CRITIC,
    ]
    
    for role in specialized_roles:
        agents[role] = create_agent(role, llm_client)
    
    return agents


__all__ = ["Agent", "create_agent", "create_all_agents"]
