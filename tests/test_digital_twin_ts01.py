"""
Digital Twin smoke test: TS-01 happy path.
Runs against real backend at localhost:8000.
"""
import asyncio
import pytest
from tests.digital_twin.orchestrator import DigitalTwinOrchestrator
from tests.digital_twin.mocks.twin_config import TwinConfig


@pytest.mark.asyncio
async def test_ts01_happy_path(perfect_config):
    """TS-01: Single filer, perfect mode — all services nominal."""
    orchestrator = DigitalTwinOrchestrator(config=perfect_config)
    result = await orchestrator.run_scenario("TS-01")

    assert result.passed, f"TS-01 failed: {result.failures}"
    assert result.liability_accurate, f"Liability delta ${result.liability_delta_usd:.2f} too large"
    assert result.flag_precision >= 0.95, f"Flag precision {result.flag_precision:.2f} below threshold"


@pytest.mark.asyncio
async def test_calculator_basic():
    """Unit test: Tax calculator produces correct liability for TS-01 profile."""
    import sys
    sys.path.insert(0, "/Users/Francisco_Reveriano/Documents/Demos/Tax.AI")
    from backend.tools.calculator_tool import TaxCalculator

    calc = TaxCalculator()
    result = calc.compute_federal_tax(
        income=55000.0,
        filing_status="Single",
        year=2025,
        use_standard_deduction=True,
    )

    # Taxable income = 55000 - 15750 = 39250
    # 10% on 11925 = 1192.5
    # 12% on 27325 = 3279
    # Total = 4471.5
    assert result["taxable_income"] == 39250.0
    assert result["federal_tax"] == pytest.approx(4471.5, abs=10.0)
