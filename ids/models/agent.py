"""Agent models and definitions"""

from enum import Enum
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from .cross import CrossScore


class AgentRole(str, Enum):
    """Agent roles in Parliament"""
    GENERALIST = "generalist"
    DEVELOPER_PROGRESSIVE = "developer_progressive"
    DEVELOPER_CRITIC = "developer_critic"
    ARCHITECT_PROGRESSIVE = "architect_progressive"
    ARCHITECT_CRITIC = "architect_critic"
    SRE_PROGRESSIVE = "sre_progressive"
    SRE_CRITIC = "sre_critic"
    SOURCER = "sourcer"


class AgentResponse(BaseModel):
    """Response from a single agent during deliberation round"""
    agent_id: AgentRole = Field(description="Agent role identifier")
    
    # Full LLM response
    raw_response: str = Field(description="Complete response from LLM before parsing")
    
    # Parsed components
    cross_score: CrossScore = Field(description="CROSS scoring")
    proposed_approach: str = Field(description="Detailed solution proposal")
    concerns: List[str] = Field(default_factory=list, description="Specific concerns identified")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
