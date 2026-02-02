"""Application settings and configuration"""

from typing import List, Optional
from pydantic import Field
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
    
    # Projects
    projects_root: str = Field(default="/projects", description="Root path for projects")
    default_project: str = Field(default="general", description="Default project context")
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    def get_allowed_users(self) -> List[int]:
        """Parse allowed Telegram user IDs"""
        return [int(uid.strip()) for uid in self.allowed_telegram_users.split(",")]
    
    @property
    def chromadb_url(self) -> str:
        """ChromaDB HTTP URL"""
        return f"http://{self.chromadb_host}:{self.chromadb_port}"


# Global settings instance
settings = Settings()
