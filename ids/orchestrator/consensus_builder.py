"""Consensus builder - evaluates CROSS scores and determines deliberation outcome"""

import yaml
from pathlib import Path
from typing import List
from ids.models import (
    AgentResponse,
    MergedCross,
    DecisionResult,
    RoundResult,
    DevSession
)
from ids.utils import get_logger

logger = get_logger(__name__)


class ConsensusBuilder:
    """
    Evaluates CROSS scores and determines if consensus is reached.
    Uses tunable thresholds from thresholds.yaml.
    """

    def __init__(self):
        self.thresholds = self._load_thresholds()
        logger.info("consensus_builder_initialized")

    def _load_thresholds(self) -> dict:
        """Load thresholds from YAML configuration"""
        config_path = Path(__file__).parent.parent / "config" / "thresholds.yaml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        logger.info("thresholds_loaded", config=config)
        return config

    def evaluate_round(
        self,
        round_result: RoundResult,
        round_num: int,
        session: DevSession
    ) -> tuple[DecisionResult, str]:
        """
        Evaluate a deliberation round and determine outcome.

        Args:
            round_result: Results from the round
            round_num: Current round number
            session: Full session for dead-end detection

        Returns:
            Tuple of (DecisionResult, reasoning_string)
        """
        merged = round_result.merged_cross

        logger.info(
            "evaluating_round",
            round_num=round_num,
            avg_confidence=merged.avg_confidence,
            max_risk=merged.max_risk,
            avg_outcome=merged.avg_outcome
        )

        # Check if consensus is reached
        if self._check_consensus(merged, round_num):
            reasoning = (
                f"Consensus reached in round {round_num}. "
                f"Confidence: {merged.avg_confidence:.1f}, "
                f"Risk: {merged.max_risk:.1f}, "
                f"Outcome: {merged.avg_outcome:.1f}. "
                f"All thresholds met with good agreement (std_conf: {merged.std_confidence:.1f}, "
                f"std_outcome: {merged.std_outcome:.1f})."
            )
            logger.info("consensus_reached", round_num=round_num)
            return DecisionResult.CONSENSUS, reasoning

        # Check if dead-end
        if self._detect_dead_end(session, round_num):
            reasoning = (
                f"Dead-end detected after {round_num} round(s). "
                f"Unable to reach consensus. Confidence: {merged.avg_confidence:.1f}, "
                f"Risk: {merged.max_risk:.1f}. Need user guidance to proceed."
            )
            logger.info("dead_end_detected", round_num=round_num)
            return DecisionResult.DEAD_END, reasoning

        # Continue to next round
        reasoning = (
            f"Continuing to round {round_num + 1}. "
            f"Confidence: {merged.avg_confidence:.1f}, "
            f"Risk: {merged.max_risk:.1f}, "
            f"Outcome: {merged.avg_outcome:.1f}. "
            f"Making progress but not yet meeting all consensus criteria."
        )
        logger.info("continuing_deliberation", round_num=round_num)
        return DecisionResult.CONTINUE, reasoning

    def _check_consensus(self, merged: MergedCross, round_num: int) -> bool:
        """
        Check if consensus criteria are met.

        Consensus requires:
        1. Confidence >= threshold
        2. Risk <= acceptable
        3. Outcome >= minimum
        4. Agreement (low std deviation)
        """
        consensus_config = self.thresholds.get("consensus", {})

        # Get thresholds for this round
        confidence_threshold = self._get_round_threshold(
            consensus_config.get("confidence_threshold", {}),
            round_num,
            default=70.0
        )

        max_risk = self._get_round_threshold(
            consensus_config.get("max_acceptable_risk", {}),
            round_num,
            default=40.0
        )

        min_outcome = self._get_round_threshold(
            consensus_config.get("min_outcome_score", {}),
            round_num,
            default=60.0
        )

        max_confidence_std = consensus_config.get("max_confidence_std", 15.0)
        max_outcome_std = consensus_config.get("max_outcome_std", 15.0)

        # Check all criteria
        checks = {
            "confidence": merged.avg_confidence >= confidence_threshold,
            "risk": merged.max_risk <= max_risk,
            "outcome": merged.avg_outcome >= min_outcome,
            "confidence_agreement": merged.std_confidence <= max_confidence_std,
            "outcome_agreement": merged.std_outcome <= max_outcome_std
        }

        logger.info(
            "consensus_checks",
            round_num=round_num,
            checks=checks,
            thresholds={
                "confidence": confidence_threshold,
                "risk": max_risk,
                "outcome": min_outcome
            }
        )

        # All checks must pass
        return all(checks.values())

    def _get_round_threshold(
        self,
        threshold_dict: dict,
        round_num: int,
        default: float
    ) -> float:
        """Get threshold for specific round number"""
        # Try specific round
        key = f"round_{round_num}"
        if key in threshold_dict:
            return threshold_dict[key]

        # Fall back to round 3 if beyond
        if round_num > 3:
            return threshold_dict.get("round_3", default)

        return default

    def _detect_dead_end(self, session: DevSession, round_num: int) -> bool:
        """
        Detect if deliberation has reached a dead-end.

        Dead-end indicators:
        1. Confidence declining across rounds
        2. Persistent high risks
        3. No progress toward consensus
        """
        if round_num < 2:
            return False  # Need at least 2 rounds to detect patterns

        dead_end_config = self.thresholds.get("dead_end", {})

        # Check confidence decline
        if len(session.rounds) >= 2:
            prev_confidence = session.rounds[-2].merged_cross.avg_confidence
            curr_confidence = session.rounds[-1].merged_cross.avg_confidence

            decline_threshold = dead_end_config.get("confidence_decline_threshold", 10.0)

            if prev_confidence - curr_confidence > decline_threshold:
                logger.info(
                    "dead_end_confidence_decline",
                    prev=prev_confidence,
                    curr=curr_confidence
                )
                return True

        # Check persistent high risk
        persistent_risk_rounds = dead_end_config.get("persistent_risk_rounds", 2)
        if len(session.rounds) >= persistent_risk_rounds:
            recent_rounds = session.rounds[-persistent_risk_rounds:]
            high_risk_threshold = 60.0  # Consider 60+ as high risk

            all_high_risk = all(
                r.merged_cross.max_risk > high_risk_threshold
                for r in recent_rounds
            )

            if all_high_risk:
                logger.info("dead_end_persistent_high_risk")
                return True

        return False

    def merge_cross_scores(self, all_responses: List[AgentResponse]) -> MergedCross:
        """
        Merge CROSS scores from all agents (specialists + generalist).

        Args:
            all_responses: All agent responses from this round

        Returns:
            Merged CROSS scores
        """
        scores = [r.cross_score for r in all_responses]
        merged = MergedCross.from_scores(scores)

        logger.info(
            "scores_merged",
            agent_count=len(all_responses),
            avg_confidence=merged.avg_confidence,
            max_risk=merged.max_risk,
            avg_outcome=merged.avg_outcome,
            std_confidence=merged.std_confidence
        )

        return merged
