"""Project/context models"""

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class Project(BaseModel):
    """
    Project represents a context domain for deliberation.
    Can be a software project, business domain, or any decision context.
    """
    project_id: str = Field(description="Unique project identifier")
    name: str = Field(description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")
    path: Optional[str] = Field(default=None, description="Filesystem path (if applicable)")

    telegram_user_id: int = Field(description="Owner's Telegram user ID")

    # Parliament prompt URLs (fetched at runtime; fallback to local persona files)
    generalist_prompt_url: Optional[str] = Field(default=None, description="URL to generalist system prompt")
    sourcer_prompt_url: Optional[str] = Field(default=None, description="URL to sourcer system prompt")
    specialist_prompt_urls: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of specialist key ('1', '2', ...) to prompt URL"
    )

    # Response size limits in tokens
    specialist_max_tokens: int = Field(default=1000, description="Max tokens for specialist responses")
    generalist_max_tokens: int = Field(default=2000, description="Max tokens for generalist responses")
    sourcer_max_tokens: int = Field(default=3000, description="Max tokens for sourcer responses")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
