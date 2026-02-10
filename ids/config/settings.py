"""Application settings and configuration"""

from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Telegram Configuration
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    allowed_telegram_users: str = Field(..., description="Comma-separated user IDs")
    
    # LLM API Keys
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    anthropic_api_key: str = Field(..., description="Anthropic Claude API key")
    
    # LLM Model Configuration
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model name")
    claude_model: str = Field(default="claude-sonnet-4-20250514", description="Claude model name")
    
    # Storage Configuration
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    mongodb_db: str = Field(default="ids")
    chromadb_host: str = Field(default="localhost")
    chromadb_port: int = Field(default=8000)
    redis_url: str = Field(default="redis://localhost:6379")
    
    # Behavior Configuration
    round_logging: bool = Field(default=True, description="Show detailed round updates")
    max_rounds: int = Field(default=3, description="Maximum deliberation rounds")
    max_iterations: int = Field(default=10, description="Maximum implementation iterations")
    
    # Agent Execution Configuration
    # PARALLEL_AGENTS=false (default) = sequential, avoids rate limits
    # SEQUENTIAL_AGENTS=true = alternative way to force sequential (overrides PARALLEL_AGENTS)
    parallel_agents: bool = Field(default=False, description="Execute agents in parallel (requires higher API quota)")
    sequential_agents: Optional[bool] = Field(default=None, description="If true, force sequential execution (overrides PARALLEL_AGENTS)")
    agent_delay_seconds: float = Field(default=2.0, description="Delay between sequential agent calls to avoid rate limits")
    
    # Agent Enable/Disable Configuration
    # Set to false to disable specific specialist agents from parliament
    developer_progressive_enabled: bool = Field(default=True, description="Enable Developer Progressive agent")
    developer_critic_enabled: bool = Field(default=True, description="Enable Developer Critic agent")
    architect_progressive_enabled: bool = Field(default=True, description="Enable Architect Progressive agent")
    architect_critic_enabled: bool = Field(default=True, description="Enable Architect Critic agent")
    sre_progressive_enabled: bool = Field(default=True, description="Enable SRE Progressive agent")
    sre_critic_enabled: bool = Field(default=True, description="Enable SRE Critic agent")
    
    # Projects
    projects_root: str = Field(default="/projects", description="Root path for projects")
    default_project: str = Field(default="general", description="Default project context")
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    @model_validator(mode="after")
    def apply_sequential_override(self) -> "Settings":
        """If SEQUENTIAL_AGENTS=true, force parallel_agents to False (avoids rate limits)"""
        if self.sequential_agents is True:
            object.__setattr__(self, "parallel_agents", False)
        return self

    def get_allowed_users(self) -> List[int]:
        """Parse allowed Telegram user IDs"""
        return [int(uid.strip()) for uid in self.allowed_telegram_users.split(",")]
    
    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled specialist agent roles"""
        from ids.models import AgentRole
        
        enabled = []
        agent_settings = {
            AgentRole.DEVELOPER_PROGRESSIVE: self.developer_progressive_enabled,
            AgentRole.DEVELOPER_CRITIC: self.developer_critic_enabled,
            AgentRole.ARCHITECT_PROGRESSIVE: self.architect_progressive_enabled,
            AgentRole.ARCHITECT_CRITIC: self.architect_critic_enabled,
            AgentRole.SRE_PROGRESSIVE: self.sre_progressive_enabled,
            AgentRole.SRE_CRITIC: self.sre_critic_enabled,
        }
        
        for role, is_enabled in agent_settings.items():
            if is_enabled:
                enabled.append(role)
        
        return enabled

    @property
    def chromadb_url(self) -> str:
        """ChromaDB HTTP URL"""
        return f"http://{self.chromadb_host}:{self.chromadb_port}"


# Global settings instance
settings = Settings()
