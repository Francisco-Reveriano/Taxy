"""Shared pytest fixtures for E2E tax scenario tests."""
import tempfile
from pathlib import Path

import pytest

from backend.tools.calculator_tool import TaxCalculator
from backend.services.scoring_engine import ScoringEngine


@pytest.fixture
def tmp_audit_dir(tmp_path):
    """Temporary directory for JSONL audit logs and generated reports."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    return audit_dir


@pytest.fixture
def calculator():
    """TaxCalculator instance."""
    return TaxCalculator()


@pytest.fixture
def scoring_engine():
    """ScoringEngine instance."""
    return ScoringEngine()
