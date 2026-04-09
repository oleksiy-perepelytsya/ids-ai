"""Session and round models"""

from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .agent import AgentResponse
from .cross import MergedCross
from .consensus import DecisionResult


class SourcerLog(BaseModel):
    """Record of a single /sourcer invocation"""
    log_id: str = Field(description="Unique log identifier")
    project_id: str
    user_id: int = Field(description="User who invoked the sourcer")
    original_query: str = Field(description="Raw query from the user")
    generated_prompt: Optional[str] = Field(default=None, description="Prompt produced by genprompt model")
    genprompt_model: Optional[str] = Field(default=None, description="Model used for prompt generation")
    search_query: str = Field(description="Query actually sent to sourcer (original or generated)")
    sourcer_model: str = Field(description="Model used for the sourcer call")
    response: str = Field(description="Sourcer response text")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PromptLibraryEntry(BaseModel):
    """A generated specialist system prompt stored for reuse"""
    entry_id: str
    project_id: str
    role_name: str = Field(description="Specialist role identifier, e.g. 'marine_biologist'")
    prompt: str = Field(description="Full system prompt text")
    generator_model: str = Field(description="Model that generated this prompt")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


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

    # Summary of what was deliberated this round
    generalist_prompt: str = Field(description="Summary of round task/context sent to parliament")
    generalist_response: AgentResponse = Field(description="Generalist's synthesis response")

    # Specialist responses
    agent_responses: List[AgentResponse] = Field(description="All specialist agent responses")

    # Aggregated results
    merged_cross: MergedCross = Field(description="Merged CROSS from all agents including generalist")
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
    user_id: int = Field(description="User who created session")
    chat_id: int = Field(description="Chat/channel ID for responses")
    project_id: str = Field(description="Project ID this session belongs to")
    project_name: Optional[str] = Field(default=None, description="Project name (display only)")

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
