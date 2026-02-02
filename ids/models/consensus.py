"""Consensus and decision models"""

from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field


class DecisionResult(str, Enum):
    """Possible deliberation outcomes"""
    CONSENSUS = "consensus"  # Agreement reached, proceed
    CONTINUE = "continue"    # Continue to next round
    DEAD_END = "dead_end"    # Cannot reach consensus, need user input


class ConsensusThresholds(BaseModel):
    """
    Tunable thresholds for consensus detection.
    Start strict and tune based on learning data.
    """
    # Confidence thresholds by round (stricter early on)
    confidence_threshold: Dict[int, float] = Field(
        default={
            1: 85.0,  # Round 1: Very strict
            2: 75.0,  # Round 2: Moderate
            3: 70.0   # Round 3: More lenient
        }
    )
    
    # Maximum acceptable risk by round
    max_acceptable_risk: Dict[int, float] = Field(
        default={
            1: 20.0,  # Round 1: Very risk-averse
            2: 30.0,  # Round 2: Moderate risk ok
            3: 40.0   # Round 3: Higher risk acceptable
        }
    )
    
    # Minimum outcome score by round
    min_outcome_score: Dict[int, float] = Field(
        default={
            1: 80.0,  # Round 1: Expect excellent
            2: 70.0,  # Round 2: Good outcome
            3: 60.0   # Round 3: Acceptable outcome
        }
    )
    
    # Agreement thresholds (standard deviation limits)
    max_confidence_std: float = Field(default=15.0, description="Max std dev in confidence")
    max_outcome_std: float = Field(default=15.0, description="Max std dev in outcome")
    
    def get_confidence_threshold(self, round_num: int) -> float:
        """Get confidence threshold for specific round"""
        return self.confidence_threshold.get(round_num, self.confidence_threshold[3])
    
    def get_risk_threshold(self, round_num: int) -> float:
        """Get risk threshold for specific round"""
        return self.max_acceptable_risk.get(round_num, self.max_acceptable_risk[3])
    
    def get_outcome_threshold(self, round_num: int) -> float:
        """Get outcome threshold for specific round"""
        return self.min_outcome_score.get(round_num, self.min_outcome_score[3])
