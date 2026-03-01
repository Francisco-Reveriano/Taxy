"""TwinConfig — shared configuration for digital twin tests."""
from dataclasses import dataclass


@dataclass
class TwinConfig:
    mistral_mode: str = "perfect"   # perfect, realistic, degraded, failure
    claude_mode: str = "accurate_high"  # accurate_high, accurate_low, hallucinated, slow, failure
    openai_mode: str = "accurate"   # accurate, no_retrieval, failure
    backend_base_url: str = "http://localhost:8000"
    mistral_mock_url: str = "http://localhost:8001"
    claude_mock_url: str = "http://localhost:8002"
    openai_mock_url: str = "http://localhost:8003"
    timeout_seconds: int = 30
