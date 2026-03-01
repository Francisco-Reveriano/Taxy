"""
Claude API Mock Server — FastAPI on port 8002.
Modes: accurate_high, accurate_low, hallucinated, slow, failure.
"""
import asyncio
import json
import re
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any

app = FastAPI(title="Claude API Mock")

_mode = "accurate_high"

PROFILE_RESPONSES = {
    "TS-01": {
        "estimated_liability": 4616.00,
        "effective_tax_rate": 8.39,
        "applicable_deductions": [{"name": "Standard Deduction", "amount": 14600}],
        "applicable_credits": [],
        "advisory_notes": ["Consider contributing to IRA to reduce taxable income"],
        "confidence_level": "High",
        "confidence_rationale": "Clear W-2 wages, standard deduction applies",
    },
    "TS-02": {
        "estimated_liability": 12106.00,
        "effective_tax_rate": 8.97,
        "applicable_deductions": [{"name": "Itemized Deductions", "amount": 35000}],
        "applicable_credits": [{"name": "Child Tax Credit", "amount": 2000}],
        "advisory_notes": ["Itemized exceeds standard deduction — good choice"],
        "confidence_level": "High",
        "confidence_rationale": "Multiple income sources, itemized deductions clearly exceed standard",
    },
    "TS-03": {
        "estimated_liability": 9441.00,
        "effective_tax_rate": 11.80,
        "applicable_deductions": [{"name": "Standard Deduction", "amount": 14600}],
        "applicable_credits": [{"name": "Earned Income Credit", "amount": 500}],
        "advisory_notes": ["Self-employment tax applies; consider quarterly estimates"],
        "confidence_level": "High",
        "confidence_rationale": "Schedule C income, standard deduction, EIC eligible",
    },
    "TS-04": {
        "estimated_liability": 117374.75,
        "effective_tax_rate": 23.47,
        "applicable_deductions": [{"name": "Itemized Deductions", "amount": 80000}],
        "applicable_credits": [],
        "advisory_notes": ["SALT cap of $10,000 may limit state/local deduction"],
        "confidence_level": "High",
        "confidence_rationale": "High income through 35% bracket, itemized deductions",
    },
    "TS-05": {
        "estimated_liability": 3832.00,
        "effective_tax_rate": 5.90,
        "applicable_deductions": [{"name": "Standard Deduction", "amount": 29200}],
        "applicable_credits": [],
        "advisory_notes": ["Social Security benefits may be partially taxable"],
        "confidence_level": "High",
        "confidence_rationale": "MFJ retiree, standard deduction, straightforward",
    },
}

DEFAULT_RESPONSE = PROFILE_RESPONSES["TS-01"]


class MessageRequest(BaseModel):
    model: str
    max_tokens: int
    messages: List[dict]
    system: Optional[str] = None
    tools: Optional[List[Any]] = None


def _detect_profile(messages: List[dict]) -> dict:
    """Extract profile ID from message content to return the right response."""
    full_text = " ".join(
        str(m.get("content", "")) for m in messages
    ).upper()
    for pid in sorted(PROFILE_RESPONSES.keys(), key=lambda x: -len(x)):
        if pid in full_text:
            return PROFILE_RESPONSES[pid]

    for pid, data in PROFILE_RESPONSES.items():
        liability_str = f"{data['estimated_liability']:.2f}"
        if liability_str in full_text:
            return data

    return DEFAULT_RESPONSE


@app.get("/health")
def health():
    return {"status": "ok", "mode": _mode}


@app.post("/v1/messages")
async def create_message(req: MessageRequest):
    global _mode

    if _mode == "failure":
        raise HTTPException(status_code=503, detail="Claude unavailable")

    if _mode == "slow":
        await asyncio.sleep(5)

    if _mode in ("accurate_high", "slow"):
        profile_data = _detect_profile(req.messages)
        response_data = {**profile_data, "confidence_level": "High"}
    elif _mode == "accurate_low":
        profile_data = _detect_profile(req.messages)
        response_data = {
            **profile_data,
            "confidence_level": "Low",
            "confidence_rationale": "Insufficient document data",
            "advisory_notes": [],
        }
    else:  # hallucinated
        response_data = {
            "estimated_liability": 999999.00,
            "effective_tax_rate": 99.0,
            "applicable_deductions": [],
            "applicable_credits": [],
            "advisory_notes": ["This is a hallucinated response"],
            "confidence_level": "High",
            "confidence_rationale": "Completely fabricated",
        }

    return {
        "id": "mock-msg-001",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(response_data)}],
        "model": req.model,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 150},
    }


@app.post("/mode/{mode}")
def set_mode(mode: str):
    global _mode
    _mode = mode
    return {"mode": _mode}


def run():
    uvicorn.run(app, host="0.0.0.0", port=8002)


if __name__ == "__main__":
    run()
