"""Project/context models"""

from datetime import datetime
from typing import Optional
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
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
