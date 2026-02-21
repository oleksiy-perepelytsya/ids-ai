"""Agent models and definitions"""

from datetime import datetime
from pydantic import BaseModel, Field
from .cross import CrossScore

# Role ID constants
ROLE_GENERALIST = "generalist"
ROLE_SOURCER = "sourcer"


class AgentResponse(BaseModel):
    """Response from a single agent during deliberation round"""
    agent_id: str = Field(description="Agent role identifier (e.g. 'generalist', 'specialist_1')")
    role_name: str = Field(default="", description="Human-readable role name extracted from prompt '# Role:' header")

    # CROSS scoring
    cross_score: CrossScore = Field(description="CROSS scoring")

    # Single free-text response field
    response: str = Field(default="", description="Agent's full free-text analysis and recommendation")

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
