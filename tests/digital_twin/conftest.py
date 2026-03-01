"""Pytest fixtures for digital twin tests."""
import pytest
from tests.digital_twin.mocks.twin_config import TwinConfig


@pytest.fixture(scope="session")
def twin_config() -> TwinConfig:
    return TwinConfig()


@pytest.fixture
def perfect_config() -> TwinConfig:
    return TwinConfig(
        mistral_mode="perfect",
        claude_mode="accurate_high",
        openai_mode="accurate",
    )


@pytest.fixture
def degraded_config() -> TwinConfig:
    return TwinConfig(
        mistral_mode="degraded",
        claude_mode="accurate_low",
        openai_mode="accurate",
    )
