"""PII masking utility — shared across audit, telemetry, and LLM prompt paths."""
import re

SSN_PATTERN = re.compile(r"\b(\d{3})-(\d{2})-(\d{4})\b")
EIN_PATTERN = re.compile(r"\b\d{2}-(\d{7})\b")


def mask_pii(text: str) -> str:
    """Mask SSNs and EINs in text. Returns masked string."""
    text = SSN_PATTERN.sub(r"***-**-\3", text)
    text = EIN_PATTERN.sub(lambda m: f"**-***{m.group(1)[-4:]}", text)
    return text


def mask_pii_with_flag(text: str) -> tuple[str, bool]:
    """Mask SSNs and EINs. Returns (masked_text, was_masked)."""
    original = text
    masked = mask_pii(text)
    return masked, masked != original
