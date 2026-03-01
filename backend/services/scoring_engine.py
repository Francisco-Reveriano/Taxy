"""Dual-LLM scoring engine — compares Claude vs OpenAI results."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from backend.models.analysis_result import (
    DualAnalysisResult,
    FlagStatus,
    LLMAnalysisResult,
)

if TYPE_CHECKING:
    from backend.audit.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

GREEN_CONFIDENCE_THRESHOLD = 90.0
AMBER_CONFIDENCE_THRESHOLD = 75.0
GREEN_DELTA_THRESHOLD = 10.0  # dollars (% or absolute?)
RED_DELTA_THRESHOLD = 10.0    # percent


class ScoringEngine:
    def compare(
        self,
        claude: Optional[LLMAnalysisResult],
        openai: Optional[LLMAnalysisResult],
        session_id: str = "",
        audit_logger: Optional["AuditLogger"] = None,
    ) -> DualAnalysisResult:
        """
        Compare two LLM analysis results and compute flag status.

        Rules:
        - GREEN: both confidence ≥90 AND liability delta ≤10%
        - AMBER: either confidence <90 (but ≥75)
        - RED: liability delta >10% regardless of confidence
        - YELLOW: one provider failed/errored
        """
        flag_status = FlagStatus.AMBER
        consensus_liability: Optional[float] = None
        delta = 0.0
        rationale = ""

        # Handle failures
        claude_ok = claude is not None and claude.error is None
        openai_ok = openai is not None and openai.error is None

        if not claude_ok and not openai_ok:
            flag_status = FlagStatus.RED
            rationale = "Both LLM providers failed to produce results."
        elif not claude_ok or not openai_ok:
            flag_status = FlagStatus.YELLOW
            working = claude if claude_ok else openai
            consensus_liability = working.estimated_liability if working else None
            rationale = f"One provider failed: {'Claude' if not claude_ok else 'OpenAI'} returned an error."
        else:
            # Both succeeded — compare results
            claude_conf = claude.confidence_score
            openai_conf = openai.confidence_score

            c_liability = claude.estimated_liability
            o_liability = openai.estimated_liability

            if c_liability > 0 or o_liability > 0:
                base = max(c_liability, o_liability)
                delta = abs(c_liability - o_liability) / base * 100 if base > 0 else 0.0
            else:
                delta = 0.0

            consensus_liability = (c_liability + o_liability) / 2

            if claude_conf >= GREEN_CONFIDENCE_THRESHOLD and openai_conf >= GREEN_CONFIDENCE_THRESHOLD and delta <= GREEN_DELTA_THRESHOLD:
                flag_status = FlagStatus.GREEN
                rationale = (
                    f"Both providers confident (Claude: {claude_conf:.0f}%, OpenAI: {openai_conf:.0f}%) "
                    f"with {delta:.1f}% liability delta — strong agreement."
                )
            elif delta > RED_DELTA_THRESHOLD:
                flag_status = FlagStatus.RED
                rationale = (
                    f"Significant liability disagreement: {delta:.1f}% delta "
                    f"(Claude: ${c_liability:,.0f}, OpenAI: ${o_liability:,.0f}). "
                    f"Manual review required."
                )
            else:
                flag_status = FlagStatus.AMBER
                low_conf = []
                if claude_conf < GREEN_CONFIDENCE_THRESHOLD:
                    low_conf.append(f"Claude ({claude_conf:.0f}%)")
                if openai_conf < GREEN_CONFIDENCE_THRESHOLD:
                    low_conf.append(f"OpenAI ({openai_conf:.0f}%)")
                rationale = (
                    f"Moderate confidence: {', '.join(low_conf)} below 90% threshold. "
                    f"Liability delta: {delta:.1f}%."
                )

        # Emit scoring.comparison audit event
        if audit_logger is not None:
            from backend.audit.audit_logger import AuditEvent, AuditEventType
            c_conf = claude.confidence_score if claude_ok and claude else 0.0
            o_conf = openai.confidence_score if openai_ok and openai else 0.0
            asyncio.get_event_loop().create_task(audit_logger.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.SCORING_COMPARISON,
                agent_name="scoring_engine",
                output_summary=(
                    f"claude_conf={c_conf:.1f}%, openai_conf={o_conf:.1f}%, "
                    f"delta={delta:.1f}%"
                ),
                metadata={
                    "claude_confidence": c_conf,
                    "openai_confidence": o_conf,
                    "liability_delta": round(delta, 2),
                    "claude_liability": claude.estimated_liability if claude_ok and claude else None,
                    "openai_liability": openai.estimated_liability if openai_ok and openai else None,
                },
            )))

        return DualAnalysisResult(
            session_id=session_id,
            claude_result=claude,
            openai_result=openai,
            flag_status=flag_status,
            consensus_liability=consensus_liability,
            liability_delta=round(delta, 2),
            scoring_rationale=rationale,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
