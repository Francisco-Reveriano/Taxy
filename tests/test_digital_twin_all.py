"""
Comprehensive digital twin integration tests.
Parameterized over all 5 taxpayer profiles.
Requires a running backend at localhost:8000.
"""
import pytest

from tests.digital_twin.orchestrator import DigitalTwinOrchestrator
from tests.digital_twin.mocks.twin_config import TwinConfig


@pytest.fixture
def perfect_config() -> TwinConfig:
    return TwinConfig(
        mistral_mode="perfect",
        claude_mode="accurate_high",
        openai_mode="accurate",
    )


HAPPY_PATH_PROFILES = [
    ("TS-01", "Single filer, W-2 only"),
    ("TS-02", "MFJ, W-2 + 1099, itemized, CTC"),
    ("TS-03", "Self-employed, Schedule C, EIC"),
    ("TS-04", "High income, 35% bracket"),
    ("TS-05", "MFJ retiree, SS + pension"),
]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile_id, description",
    HAPPY_PATH_PROFILES,
    ids=[p[0] for p in HAPPY_PATH_PROFILES],
)
async def test_happy_path_all_profiles(perfect_config, profile_id, description):
    """
    Run each profile through the digital twin orchestrator against
    the live backend. All should pass with GREEN flag.
    """
    orchestrator = DigitalTwinOrchestrator(config=perfect_config)
    result = await orchestrator.run_scenario(profile_id)

    assert result.passed, (
        f"{profile_id} ({description}) failed: {result.failures}"
    )
    assert result.liability_accurate, (
        f"{profile_id} liability delta ${result.liability_delta_usd:.2f} exceeds tolerance"
    )
    assert result.flag_precision >= 0.95, (
        f"{profile_id} flag precision {result.flag_precision:.2f} below 0.95"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_degraded_config():
    """Run TS-01 with degraded OCR + low-confidence Claude."""
    config = TwinConfig(
        mistral_mode="degraded",
        claude_mode="accurate_low",
        openai_mode="accurate",
    )
    orchestrator = DigitalTwinOrchestrator(config=config)
    result = await orchestrator.run_scenario("TS-01")

    assert result.latency_p95_ms < 60000, (
        f"P95 latency {result.latency_p95_ms:.0f}ms too high"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_latency_within_bounds(perfect_config):
    """Verify P95 latency stays under 30s for a simple profile."""
    orchestrator = DigitalTwinOrchestrator(config=perfect_config)
    result = await orchestrator.run_scenario("TS-01")

    assert result.latency_p95_ms <= 30000, (
        f"P95 latency {result.latency_p95_ms:.0f}ms exceeds 30s"
    )
