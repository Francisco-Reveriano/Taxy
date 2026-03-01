"""Wizard state management endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from backend.models.wizard_state import WizardState

router = APIRouter()

# In-memory session store (sufficient for local single-user tool)
_sessions: dict[str, WizardState] = {}


@router.get("/wizard/state")
async def get_wizard_state(session_id: str):
    """Get current wizard state for a session."""
    if session_id not in _sessions:
        # Create new session
        state = WizardState(
            session_id=session_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        _sessions[session_id] = state
    return _sessions[session_id]


@router.put("/wizard/state")
async def update_wizard_state(state: WizardState):
    """Update wizard state for a session."""
    state.updated_at = datetime.now(timezone.utc).isoformat()
    _sessions[state.session_id] = state
    return state


def get_sessions() -> dict[str, WizardState]:
    """Expose session store for use by other routes."""
    return _sessions
