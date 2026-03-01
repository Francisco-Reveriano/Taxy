import asyncio
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

from backend.config import get_settings
from backend.models.tax_document import OCRField

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # seconds
MIN_ASYNC_OCR_RUNS = 10
PER_RUN_TIMEOUT_SECONDS = 30.0
BATCH_TIMEOUT_SECONDS = 90.0

# ── Standard Form Field Mappings ──

W2_BOX_MAPPING: Dict[str, Dict] = {
    "box_1": {"label": "Wages, tips, other compensation", "aliases": ["wages", "compensation", "tips"]},
    "box_2": {"label": "Federal income tax withheld", "aliases": ["federal tax", "fed tax withheld", "federal income tax"]},
    "box_3": {"label": "Social security wages", "aliases": ["ss wages", "social security wages"]},
    "box_4": {"label": "Social security tax withheld", "aliases": ["ss tax", "social security tax"]},
    "box_5": {"label": "Medicare wages and tips", "aliases": ["medicare wages"]},
    "box_6": {"label": "Medicare tax withheld", "aliases": ["medicare tax"]},
    "box_7": {"label": "Social security tips", "aliases": ["ss tips"]},
    "box_8": {"label": "Allocated tips", "aliases": ["allocated tips"]},
    "box_10": {"label": "Dependent care benefits", "aliases": ["dependent care"]},
    "box_11": {"label": "Nonqualified plans", "aliases": ["nonqualified"]},
    "box_12a": {"label": "Code/Amount 12a", "aliases": ["12a", "box 12a"]},
    "box_12b": {"label": "Code/Amount 12b", "aliases": ["12b", "box 12b"]},
    "box_12c": {"label": "Code/Amount 12c", "aliases": ["12c", "box 12c"]},
    "box_12d": {"label": "Code/Amount 12d", "aliases": ["12d", "box 12d"]},
    "box_13": {"label": "Statutory/Retirement/Third-party sick", "aliases": ["statutory", "retirement plan"]},
    "box_14": {"label": "Other", "aliases": ["other"]},
    "box_15": {"label": "State/Employer state ID", "aliases": ["state", "employer state"]},
    "box_16": {"label": "State wages", "aliases": ["state wages"]},
    "box_17": {"label": "State income tax", "aliases": ["state tax", "state income tax"]},
    "box_18": {"label": "Local wages", "aliases": ["local wages"]},
    "box_19": {"label": "Local income tax", "aliases": ["local tax", "local income tax"]},
    "box_20": {"label": "Locality name", "aliases": ["locality"]},
}

FORM_1099_INT_MAPPING: Dict[str, Dict] = {
    "box_1": {"label": "Interest income", "aliases": ["interest income", "interest"]},
    "box_2": {"label": "Early withdrawal penalty", "aliases": ["early withdrawal"]},
    "box_3": {"label": "Interest on U.S. Savings Bonds", "aliases": ["savings bonds"]},
    "box_4": {"label": "Federal income tax withheld", "aliases": ["federal tax withheld"]},
    "box_8": {"label": "Tax-exempt interest", "aliases": ["tax-exempt", "tax exempt interest"]},
}

FORM_1099_DIV_MAPPING: Dict[str, Dict] = {
    "box_1a": {"label": "Total ordinary dividends", "aliases": ["ordinary dividends", "total dividends"]},
    "box_1b": {"label": "Qualified dividends", "aliases": ["qualified dividends"]},
    "box_2a": {"label": "Total capital gain distributions", "aliases": ["capital gain", "capital gains"]},
    "box_4": {"label": "Federal income tax withheld", "aliases": ["federal tax withheld"]},
}

FORM_1099_NEC_MAPPING: Dict[str, Dict] = {
    "box_1": {"label": "Nonemployee compensation", "aliases": ["nonemployee compensation", "nec", "compensation"]},
    "box_4": {"label": "Federal income tax withheld", "aliases": ["federal tax withheld"]},
}

FORM_MAPPINGS: Dict[str, Dict[str, Dict]] = {
    "w2": W2_BOX_MAPPING,
    "1099-int": FORM_1099_INT_MAPPING,
    "1099-div": FORM_1099_DIV_MAPPING,
    "1099-nec": FORM_1099_NEC_MAPPING,
}


def _fuzzy_match_field(field_label: str, mapping: Dict[str, Dict]) -> Optional[str]:
    """Match an OCR field label to a standard box using fuzzy label match.

    Priority: exact label > exact alias > box ID > alias containment.
    Longer alias matches are preferred to avoid false positives.
    """
    label_lower = field_label.lower().strip()

    # Pass 1: Exact label match
    for box_id, info in mapping.items():
        if label_lower == info["label"].lower():
            return box_id

    # Pass 2: Exact alias match
    for box_id, info in mapping.items():
        for alias in info.get("aliases", []):
            if label_lower == alias.lower():
                return box_id

    # Pass 3: Box ID match (e.g., "box 1", "box_1")
    for box_id, info in mapping.items():
        clean_box = box_id.replace("_", " ")
        if label_lower == clean_box or label_lower == box_id:
            return box_id

    # Pass 4: Containment match — prefer longest matching alias
    best_match: Optional[str] = None
    best_len = 0
    for box_id, info in mapping.items():
        for alias in info.get("aliases", []):
            alias_lower = alias.lower()
            if alias_lower in label_lower or label_lower in alias_lower:
                if len(alias_lower) > best_len:
                    best_len = len(alias_lower)
                    best_match = box_id

    return best_match


class MistralOCRTool:
    def __init__(self):
        self._settings = get_settings()

    def _build_client(self):
        from mistralai import Mistral
        kwargs = {"api_key": self._settings.mistral_api_key}
        if not self._settings.mistral_verify_ssl:
            import httpx
            kwargs["client"] = httpx.Client(verify=False)
        return Mistral(**kwargs)

    async def process_document(self, file_path: str, file_id: str) -> List[OCRField]:
        """
        Process a document through Mistral OCR API.
        Returns list of OCRField with per-field confidence scores.
        3 retries with exponential backoff over the full async batch.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.wait_for(
                    self._run_async_batch(file_path, file_id),
                    timeout=BATCH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(f"OCR timeout on attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                else:
                    raise
            except Exception as e:
                logger.warning(f"OCR error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                else:
                    raise

        return []

    async def _run_async_batch(self, file_path: str, file_id: str) -> List[OCRField]:
        """Run at least 10 OCR passes concurrently and aggregate results."""
        tasks = [
            asyncio.create_task(
                asyncio.wait_for(
                    asyncio.to_thread(self._process_sync_single_run, file_path, file_id, i + 1),
                    timeout=PER_RUN_TIMEOUT_SECONDS,
                )
            )
            for i in range(MIN_ASYNC_OCR_RUNS)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_runs: List[List[OCRField]] = []
        error_count = 0
        for idx, result in enumerate(results, start=1):
            if isinstance(result, Exception):
                error_count += 1
                logger.warning(f"OCR async run {idx}/{MIN_ASYNC_OCR_RUNS} failed: {result}")
            else:
                successful_runs.append(result)

        logger.info(
            "OCR async batch complete for file_id=%s: requested=%s success=%s failed=%s",
            file_id,
            MIN_ASYNC_OCR_RUNS,
            len(successful_runs),
            error_count,
        )

        if not successful_runs:
            raise RuntimeError("All async OCR runs failed")

        aggregated = self._aggregate_runs(successful_runs)
        logger.info(
            "OCR aggregation complete for file_id=%s: output_fields=%s",
            file_id,
            len(aggregated),
        )
        return aggregated

    def _process_sync_single_run(self, file_path: str, file_id: str, run_number: int) -> List[OCRField]:
        """Single synchronous OCR call (run in thread pool)."""
        del file_id  # reserved for future tracing correlation
        client = self._build_client()
        path = Path(file_path)

        with open(path, "rb") as f:
            file_content = f.read()

        # Upload file to Mistral
        uploaded = client.files.upload(
            file={"file_name": path.name, "content": file_content},
            purpose="ocr",
        )

        # Mistral docs recommend OCRing uploaded PDFs via a signed document URL.
        signed_url = client.files.get_signed_url(file_id=uploaded.id)

        # Process OCR
        response = client.ocr.process(
            model=self._settings.ocr_model,
            document={"type": "document_url", "document_url": signed_url.url},
        )
        logger.debug("Completed OCR run %s for %s", run_number, path.name)

        fields = self._parse_ocr_response(response)

        # Apply standard form field mapping
        return self._apply_field_mapping(fields, path.name)

    def _normalize_value(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value.strip())
        cleaned = cleaned.replace("$", "").replace(",", "")
        return cleaned.lower()

    def _collapse_run_fields(self, fields: List[OCRField]) -> Dict[str, OCRField]:
        """Collapse duplicates in a single run to one deterministic field per name."""
        collapsed: Dict[str, OCRField] = {}
        for field in fields:
            existing = collapsed.get(field.field_name)
            if existing is None:
                collapsed[field.field_name] = field
                continue
            if (not existing.field_value and field.field_value) or (
                field.field_value and len(field.field_value) > len(existing.field_value)
            ):
                collapsed[field.field_name] = field
        return collapsed

    def _select_majority_value(self, observations: List[OCRField]) -> str:
        """
        Select most frequent non-empty value.
        Tie-breakers: higher mean confidence, then lexical order of normalized value.
        """
        votes: Dict[str, List[OCRField]] = defaultdict(list)
        for obs in observations:
            normalized = self._normalize_value(obs.field_value)
            if normalized:
                votes[normalized].append(obs)

        if not votes:
            return ""

        def sort_key(item: Tuple[str, List[OCRField]]) -> Tuple[int, float, str]:
            norm_value, group = item
            return (len(group), mean([g.confidence for g in group]), norm_value)

        winner_norm, winner_group = max(votes.items(), key=sort_key)
        winner_value = max(
            winner_group,
            key=lambda f: (f.confidence, len(f.field_value), f.field_value),
        ).field_value
        if winner_value:
            return winner_value
        return winner_norm

    def _aggregate_runs(self, run_outputs: List[List[OCRField]]) -> List[OCRField]:
        """Aggregate multi-run OCR outputs into consensus fields."""
        collapsed_runs = [self._collapse_run_fields(run) for run in run_outputs]
        ordered_names: List[str] = []
        seen = set()
        for run in collapsed_runs:
            for name in run.keys():
                if name not in seen:
                    seen.add(name)
                    ordered_names.append(name)

        grouped: Dict[str, List[OCRField]] = defaultdict(list)
        for run in collapsed_runs:
            for name, field in run.items():
                grouped[name].append(field)

        aggregated: List[OCRField] = []
        for name in ordered_names:
            observations = grouped.get(name, [])
            if not observations:
                continue
            avg_conf = mean([obs.confidence for obs in observations])
            consensus_value = self._select_majority_value(observations)

            representative = observations[0]
            aggregated.append(
                OCRField(
                    field_name=name,
                    field_value=consensus_value,
                    confidence=avg_conf,
                    page_number=representative.page_number,
                )
            )

        return aggregated

    def _apply_field_mapping(self, fields: List[OCRField], filename: str) -> List[OCRField]:
        """Match OCR fields to standard form box identifiers."""
        fname_lower = filename.lower()

        # Detect form type from filename
        mapping: Optional[Dict[str, Dict]] = None
        form_prefix = ""
        if "w-2" in fname_lower or "w2" in fname_lower:
            mapping = FORM_MAPPINGS["w2"]
            form_prefix = "w2"
        elif "1099-int" in fname_lower:
            mapping = FORM_MAPPINGS["1099-int"]
            form_prefix = "1099int"
        elif "1099-div" in fname_lower:
            mapping = FORM_MAPPINGS["1099-div"]
            form_prefix = "1099div"
        elif "1099-nec" in fname_lower or "1099" in fname_lower:
            mapping = FORM_MAPPINGS["1099-nec"]
            form_prefix = "1099nec"

        if not mapping:
            return fields

        for field in fields:
            matched_box = _fuzzy_match_field(field.field_name, mapping)
            if matched_box:
                field.field_name = f"{form_prefix}_{matched_box}"

        # Keep W-2 output shape stable for downstream consumers.
        if form_prefix == "w2":
            fields = self._ensure_schema_fields(fields, form_prefix, mapping)

        return fields

    def _ensure_schema_fields(
        self,
        fields: List[OCRField],
        form_prefix: str,
        mapping: Dict[str, Dict],
    ) -> List[OCRField]:
        """Ensure mapped outputs always include the same set of standardized fields."""
        prefixed = f"{form_prefix}_"
        canonical: Dict[str, OCRField] = {}
        passthrough: List[OCRField] = []

        for field in fields:
            if not field.field_name.startswith(prefixed):
                passthrough.append(field)
                continue

            existing = canonical.get(field.field_name)
            if existing is None:
                canonical[field.field_name] = field
                continue

            # Prefer populated values over empty/placeholder duplicates.
            if (not existing.field_value and field.field_value) or (
                field.field_value and len(field.field_value) > len(existing.field_value)
            ):
                canonical[field.field_name] = field

        stable_fields: List[OCRField] = []
        for box_id in mapping.keys():
            key = f"{form_prefix}_{box_id}"
            if key in canonical:
                stable_fields.append(canonical[key])
            else:
                stable_fields.append(
                    OCRField(
                        field_name=key,
                        field_value="",
                        confidence=0.0,
                        page_number=1,
                    )
                )

        # Preserve any extra mapped fields that are not part of the canonical mapping.
        for key, value in canonical.items():
            if key not in {f"{form_prefix}_{box_id}" for box_id in mapping.keys()}:
                stable_fields.append(value)

        return passthrough + stable_fields

    def _extract_anchor_values(self, markdown: str, page_number: int) -> List[OCRField]:
        """Extract label-adjacent values from OCR markdown for better fixed-layout parsing."""
        extracted: List[OCRField] = []
        normalized = re.sub(r"\s+", " ", markdown)
        amount_pattern = r"([0-9][0-9,]*(?:\.[0-9]{2})?)"

        # W-2 anchors (most relevant for current MVP).
        for info in W2_BOX_MAPPING.values():
            anchors = [info["label"], *info.get("aliases", [])]
            for anchor in anchors:
                pattern = re.compile(
                    rf"{re.escape(anchor)}\s*[:\-]?\s*\$?\s*{amount_pattern}",
                    re.IGNORECASE,
                )
                match = pattern.search(normalized)
                if match:
                    extracted.append(
                        OCRField(
                            field_name=info["label"],
                            field_value=match.group(1).replace(",", ""),
                            confidence=0.88,
                            page_number=page_number,
                        )
                    )
                    break

        return extracted

    def _parse_ocr_response(self, response) -> List[OCRField]:
        """Parse Mistral OCR response into OCRField list."""
        fields: List[OCRField] = []

        if not hasattr(response, "pages"):
            return fields

        for page_idx, page in enumerate(response.pages):
            if not hasattr(page, "markdown") or not page.markdown:
                continue

            page_number = page_idx + 1
            markdown = page.markdown

            # Extra anchor-based extraction improves consistency on fixed PDF templates.
            fields.extend(self._extract_anchor_values(markdown, page_number))

            # Parse key-value pairs from OCR markdown
            lines = markdown.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Try to extract field:value pairs
                if ":" in line and not line.startswith("#"):
                    parts = line.split(":", 1)
                    field_name = parts[0].strip().lstrip("-").strip()
                    field_value = parts[1].strip() if len(parts) > 1 else ""

                    if field_name and len(field_name) < 100:
                        fields.append(OCRField(
                            field_name=field_name,
                            field_value=field_value,
                            confidence=0.90,  # Mistral doesn't always return per-field confidence
                            page_number=page_number,
                        ))
                elif line and not line.startswith("|"):
                    # Store raw text line as a field
                    fields.append(OCRField(
                        field_name=f"line_{page_number}_{len(fields)}",
                        field_value=line,
                        confidence=0.85,
                        page_number=page_number,
                    ))

        return fields
