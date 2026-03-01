"""
Evaluation scorecard for digital twin test results.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EvaluationResult:
    scenario_id: str
    liability_accurate: bool
    liability_delta_usd: float
    flag_precision: float
    flag_recall: float
    latency_p95_ms: float
    passed: bool
    failures: List[str]


class Evaluator:
    LIABILITY_TOLERANCE_USD = 50.0
    FLAG_PRECISION_THRESHOLD = 0.95
    FLAG_RECALL_THRESHOLD = 1.0
    LATENCY_P95_THRESHOLD_MS = 30000.0  # 30 seconds

    def evaluate(
        self,
        scenario_id: str,
        ground_truth_liability: float,
        estimated_liability: float,
        flag_status: str,
        expected_flag: str,
        latencies_ms: List[float],
    ) -> EvaluationResult:
        failures = []

        # Liability accuracy
        delta = abs(ground_truth_liability - estimated_liability)
        liability_accurate = delta <= self.LIABILITY_TOLERANCE_USD
        if not liability_accurate:
            failures.append(
                f"Liability delta ${delta:.2f} exceeds ${self.LIABILITY_TOLERANCE_USD} tolerance"
            )

        # Flag accuracy (simplified precision/recall for single prediction)
        flag_correct = flag_status == expected_flag
        precision = 1.0 if flag_correct else 0.0
        recall = 1.0 if flag_correct else 0.0
        if not flag_correct:
            failures.append(f"Flag mismatch: expected {expected_flag}, got {flag_status}")

        # Latency P95
        if latencies_ms:
            sorted_latencies = sorted(latencies_ms)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95 = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
        else:
            p95 = 0.0

        if p95 > self.LATENCY_P95_THRESHOLD_MS:
            failures.append(f"P95 latency {p95:.0f}ms exceeds {self.LATENCY_P95_THRESHOLD_MS:.0f}ms")

        passed = len(failures) == 0

        return EvaluationResult(
            scenario_id=scenario_id,
            liability_accurate=liability_accurate,
            liability_delta_usd=delta,
            flag_precision=precision,
            flag_recall=recall,
            latency_p95_ms=p95,
            passed=passed,
            failures=failures,
        )
