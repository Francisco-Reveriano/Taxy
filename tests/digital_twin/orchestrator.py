"""
Digital Twin Orchestrator — loads YAML scenario, configures twins,
walks wizard via httpx, captures output.
"""
import asyncio
import time
from pathlib import Path
from typing import Optional

import httpx

from tests.digital_twin.evaluation import Evaluator, EvaluationResult
from tests.digital_twin.factories.taxpayer_factory import TaxpayerFactory
from tests.digital_twin.mocks.twin_config import TwinConfig


class DigitalTwinOrchestrator:
    def __init__(self, config: Optional[TwinConfig] = None):
        self._config = config or TwinConfig()
        self._evaluator = Evaluator()
        self._latencies: list[float] = []

    async def run_scenario(self, scenario_id: str) -> EvaluationResult:
        """Run a test scenario end-to-end and return evaluation result."""
        profile = TaxpayerFactory.create(scenario_id)
        tax_data = TaxpayerFactory.to_tax_data(profile)

        import uuid
        session_id = str(uuid.uuid4())

        async with httpx.AsyncClient(
            base_url=self._config.backend_base_url,
            timeout=self._config.timeout_seconds,
        ) as client:
            # Step 1: Create wizard state
            state_resp = await client.put(
                "/api/wizard/state",
                json={
                    "session_id": session_id,
                    "current_step": 1,
                    "filing_status": profile.filing_status,
                },
            )
            assert state_resp.status_code == 200, f"Wizard state failed: {state_resp.text}"

            # Step 2: Run analysis
            start = time.time()
            analysis_resp = await client.post(
                "/api/analyze",
                json={"session_id": session_id, "tax_data": tax_data},
                timeout=60.0,
            )
            latency_ms = (time.time() - start) * 1000
            self._latencies.append(latency_ms)

            if analysis_resp.status_code != 200:
                return EvaluationResult(
                    scenario_id=scenario_id,
                    liability_accurate=False,
                    liability_delta_usd=9999,
                    flag_precision=0.0,
                    flag_recall=0.0,
                    latency_p95_ms=latency_ms,
                    passed=False,
                    failures=[f"Analysis API returned {analysis_resp.status_code}: {analysis_resp.text}"],
                )

            result = analysis_resp.json()
            estimated = result.get("consensus_liability") or 0.0
            flag_status = result.get("flag_status", "AMBER")

        return self._evaluator.evaluate(
            scenario_id=scenario_id,
            ground_truth_liability=profile.ground_truth_liability,
            estimated_liability=estimated,
            flag_status=flag_status,
            expected_flag="GREEN",
            latencies_ms=self._latencies,
        )
