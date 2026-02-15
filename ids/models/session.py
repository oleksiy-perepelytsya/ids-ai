"""Session and round models"""

from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .agent import AgentResponse
from .cross import CrossScore, MergedCross
from .consensus import DecisionResult


class SessionStatus(str, Enum):
    """Session lifecycle status"""
    PENDING = "pending"       # Created, not started
    CLARIFYING = "clarifying" # Asking user for clarifications
    DELIBERATING = "deliberating"  # Active deliberation
    AWAITING_CONTINUATION = "awaiting_continuation" # Paused between rounds
    CONSENSUS = "consensus"   # Consensus reached
    DEAD_END = "dead_end"     # Needs user feedback
    COMPLETED = "completed"   # Fully complete
    CANCELLED = "cancelled"   # User cancelled


class RoundResult(BaseModel):
    """Results from a single deliberation round"""
    round_number: int = Field(description="Round number (1-indexed)")
    
    # Generalist's input to this round
    generalist_prompt: str = Field(description="Prompt sent by generalist to parliament")
    generalist_response: AgentResponse = Field(description="Generalist's full response")
    generalist_cross: CrossScore = Field(description="Generalist's initial CROSS score (duplicated from response)")
    
    # Parliament member responses
    agent_responses: List[AgentResponse] = Field(description="All agent responses")
    
    # Aggregated results
    merged_cross: MergedCross = Field(description="Merged CROSS from all agents")
    decision: DecisionResult = Field(description="Round outcome decision")
    
    # Decision reasoning
    decision_reasoning: str = Field(default="", description="Why this decision was made")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DevSession(BaseModel):
    """Development/deliberation session"""
    session_id: str = Field(description="Unique session identifier")
    telegram_user_id: int = Field(description="Telegram user who created session")
    telegram_chat_id: int = Field(description="Telegram chat ID")
    project_name: Optional[str] = Field(default=None, description="Project context")
    
    task: str = Field(description="User's question/task")
    context: str = Field(default="", description="Additional context and user guidance")
    
    rounds: List[RoundResult] = Field(default_factory=list, description="Deliberation rounds")
    status: SessionStatus = Field(default=SessionStatus.PENDING)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_round(self, round_result: RoundResult) -> None:
        """Add a round result to session"""
        self.rounds.append(round_result)
        self.updated_at = datetime.utcnow()
    
    def get_current_round_number(self) -> int:
        """Get next round number"""
        return len(self.rounds) + 1
