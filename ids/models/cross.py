"""CROSS Scoring System: Confidence, Risk, Outcome, Scoring"""

from typing import List
from pydantic import BaseModel, Field
from statistics import mean, stdev


class CrossScore(BaseModel):
    """
    CROSS: Confidence, Risk, Outcome Scoring
    
    All scores are 0.0-100.0:
    - Confidence: How confident in the proposed solution (0=uncertain, 100=certain)
    - Risk: Risk level (0=no risk, 100=critical risk)
    - Outcome: Expected positive outcome (0=poor, 100=excellent)
    """
    confidence: float = Field(ge=0.0, le=100.0, description="Confidence in solution")
    risk: float = Field(ge=0.0, le=100.0, description="Risk level (0=safe, 100=critical)")
    outcome: float = Field(ge=0.0, le=100.0, description="Expected outcome quality")
    explanation: str = Field(min_length=10, description="Reasoning behind scores")


class MergedCross(BaseModel):
    """
    Merged CROSS scores from multiple agents.
    Used by Generalist to make consensus decisions.
    """
    avg_confidence: float = Field(description="Average confidence across all agents")
    max_risk: float = Field(description="Maximum risk identified by any agent")
    avg_outcome: float = Field(description="Average expected outcome")
    std_confidence: float = Field(description="Standard deviation of confidence (agreement)")
    std_outcome: float = Field(description="Standard deviation of outcome (agreement)")
    
    @classmethod
    def from_scores(cls, scores: List[CrossScore]) -> "MergedCross":
        """Create merged score from list of agent scores"""
        if not scores:
            raise ValueError("Cannot merge empty score list")
        
        confidences = [s.confidence for s in scores]
        risks = [s.risk for s in scores]
        outcomes = [s.outcome for s in scores]
        
        return cls(
            avg_confidence=mean(confidences),
            max_risk=max(risks),
            avg_outcome=mean(outcomes),
            std_confidence=stdev(confidences) if len(confidences) > 1 else 0.0,
            std_outcome=stdev(outcomes) if len(outcomes) > 1 else 0.0
        )
