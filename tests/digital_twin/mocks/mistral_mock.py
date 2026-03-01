"""
Mistral OCR Mock Server — FastAPI on port 8001.
Modes: perfect, realistic, degraded, failure.
"""
import re
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Mistral OCR Mock")

_mode = "perfect"

PROFILE_OCR_DATA = {
    "TS-01": {"wages": 55000.00, "withheld": 6000.00, "employer": "ACME Corporation", "ssn_last4": "1234"},
    "TS-02": {"wages": 120000.00, "withheld": 18000.00, "employer": "Global Industries", "ssn_last4": "5678"},
    "TS-03": {"wages": 0.00, "withheld": 0.00, "employer": "Self-Employed", "ssn_last4": "9012"},
    "TS-04": {"wages": 450000.00, "withheld": 90000.00, "employer": "MegaCorp Inc.", "ssn_last4": "3456"},
    "TS-05": {"wages": 0.00, "withheld": 0.00, "employer": "Retired — N/A", "ssn_last4": "7890"},
}

DEFAULT_OCR = PROFILE_OCR_DATA["TS-01"]


class OCRRequest(BaseModel):
    model: str
    document: dict


def _detect_profile(req: OCRRequest) -> dict:
    """Try to detect the profile from the document metadata or filename."""
    doc_str = str(req.document).upper()
    for pid in PROFILE_OCR_DATA:
        if pid in doc_str:
            return PROFILE_OCR_DATA[pid]
    return DEFAULT_OCR


def _render_perfect(data: dict) -> str:
    return (
        f"Box 1 - Wages: ${data['wages']:,.2f}\n"
        f"Box 2 - Federal Income Tax Withheld: ${data['withheld']:,.2f}\n"
        f"Employer Name: {data['employer']}\n"
        f"Employee SSN: ***-**-{data['ssn_last4']}\n"
    )


def _render_realistic(data: dict) -> str:
    wages_str = f"${data['wages']:,.2f}"
    wages_str = wages_str.replace("0", "O", 1)
    return (
        f"Box 1 - Wages: {wages_str}\n"
        f"Box 2 - Federal lncome Tax Withheld: ${data['withheld']:,.2f}\n"
        f"Employer Name: {data['employer']}\n"
        f"Employee SSN: ***-**-{data['ssn_last4']}\n"
    )


def _render_degraded(data: dict) -> str:
    return (
        f"Box 1 - Wag3s: $##,###.00\n"
        f"Box 2 - F3d3ral Tax: $???.00\n"
        f"Emp10yer: [ILLEGIBLE]\n"
        f"SSN: ***-**-????\n"
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": _mode}


@app.post("/v1/ocr")
def process_ocr(req: OCRRequest):
    global _mode
    if _mode == "failure":
        raise HTTPException(status_code=500, detail="OCR service unavailable")

    data = _detect_profile(req)

    if _mode == "perfect":
        markdown = _render_perfect(data)
    elif _mode == "realistic":
        markdown = _render_realistic(data)
    else:
        markdown = _render_degraded(data)

    pages = [{"markdown": markdown, "index": 0}]
    return {"pages": pages, "model": req.model}


@app.post("/mode/{mode}")
def set_mode(mode: str):
    global _mode
    _mode = mode
    return {"mode": _mode}


def run():
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    run()
