import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend/
FORM_OUTPUT_DIR = _BACKEND_DIR / "forms" / "output"
FORM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FIELD_MAP_PATH = _BACKEND_DIR / "forms" / "form1040_field_map.json"

_FORM_1040_STATUS: dict[str, dict[str, Any]] = {}


def get_form1040_status(session_id: str) -> Optional[dict[str, Any]]:
    return _FORM_1040_STATUS.get(session_id)


class Form1040Tool:
    """
    Generates a filled 1040 PDF from normalized tax data.
    Success only occurs when required semantic fields are present and written.
    """

    REQUIRED_SEMANTIC_FIELDS = [
        "first_name",
        "last_name",
        "ssn",
        "filing_status",
        "taxable_income",
        "total_tax",
        "federal_tax_withheld",
    ]

    # Map filing status values to their specific checkbox field names on the IRS 1040
    FILING_STATUS_CHECKBOXES = {
        "Single": "topmostSubform[0].Page1[0].c1_1[0]",
        "Married Filing Jointly": "topmostSubform[0].Page1[0].c1_2[0]",
        "Married Filing Separately": "topmostSubform[0].Page1[0].c1_3[0]",
        "Head of Household": "topmostSubform[0].Page1[0].c1_4[0]",
        "Qualifying Surviving Spouse": "topmostSubform[0].Page1[0].c1_5[0]",
    }

    FIELD_ALIASES = {
        "first_name": ["firstname", "first", "givenname", "taxpayerfirstname"],
        "last_name": ["lastname", "last", "surname", "taxpayerlastname"],
        "ssn": ["ssn", "socialsecurity", "socialsecuritynumber"],
        "spouse_first_name": ["spousefirstname", "spousefirst"],
        "spouse_last_name": ["spouselastname", "spouselast"],
        "spouse_ssn": ["spousessn", "spousesocialsecurity"],
        "address": ["address", "street"],
        "city": ["city"],
        "state": ["state"],
        "zip": ["zip", "zipcode", "postalcode"],
        "filing_status": ["filingstatus", "status"],
        "tax_year": ["taxyear", "year"],
        "wages": ["wages", "w2wages", "salaries", "wagestips"],
        "total_income": ["totalincome", "income"],
        "adjustments": ["adjustments", "adjustmentstoincome"],
        "adjusted_gross_income": ["agi", "adjustedgrossincome"],
        "standard_deduction": ["standarddeduction"],
        "total_deductions": ["totaldeductions"],
        "taxable_income": ["taxableincome"],
        "tax": ["taxfromtables", "line16tax"],
        "total_tax": ["totaltax", "estimatedliability", "estimatedtaxliability", "federaltax"],
        "federal_tax_withheld": ["federaltaxwithheld", "withheld", "withholding"],
        "refund_amount": ["refund", "refundamount"],
        "amount_owed": ["amountowed", "owed", "balanceowed"],
    }

    def __init__(self):
        self._settings = get_settings()

    def introspect_template_fields(self, template_path: Optional[str] = None) -> Dict[str, Any]:
        resolved_template = self._resolve_template_path(template_path)

        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError(
                "pypdf is not installed. Add pypdf to requirements and install dependencies."
            ) from exc

        try:
            reader = PdfReader(str(resolved_template))
        except Exception as exc:
            raise RuntimeError(f"Failed to read 1040 template: {exc}") from exc

        raw_fields = reader.get_fields() or {}
        if not raw_fields:
            raise ValueError("Template has no AcroForm fields. Provide a fillable 1040 template.")

        template_field_names = list(raw_fields.keys())
        explicit_map = self._load_field_map()
        semantic_to_pdf_field = self._resolve_field_mapping(template_field_names, explicit_map)

        # Build inverse index for quick "which semantic keys target this PDF field" lookup.
        inverse_mapping: dict[str, list[str]] = {}
        for semantic_key, pdf_field_name in semantic_to_pdf_field.items():
            inverse_mapping.setdefault(pdf_field_name, []).append(semantic_key)

        fields: list[dict[str, Any]] = []
        for index, (name, meta) in enumerate(raw_fields.items()):
            pdf_type = str(getattr(meta, "field_type", "") or "")
            if not pdf_type:
                try:
                    # Compatibility fallback for pypdf field wrappers.
                    pdf_type = str(meta.get("/FT", "")) if hasattr(meta, "get") else ""
                except Exception:
                    pdf_type = ""

            fields.append(
                {
                    "index": index,
                    "name": name,
                    "normalized_name": self._normalize(name),
                    "pdf_type": pdf_type,
                    "mapped_semantic_keys": sorted(inverse_mapping.get(name, [])),
                }
            )

        required_missing_mapping = [
            key for key in self.REQUIRED_SEMANTIC_FIELDS if not semantic_to_pdf_field.get(key)
        ]

        return {
            "template_file": resolved_template.name,
            "field_count": len(fields),
            "fields": fields,
            "semantic_mapping": {
                "required_semantic_fields": list(self.REQUIRED_SEMANTIC_FIELDS),
                "required_missing_mapping": required_missing_mapping,
                "resolved_semantic_to_pdf_field": semantic_to_pdf_field,
                "explicit_map_keys": sorted(
                    [k for k, v in explicit_map.items() if self._has_value(v)]
                ),
            },
        }

    def generate_form(
        self,
        session_id: str,
        tax_data: Dict[str, Any],
        template_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not session_id:
            return self._record_failure(session_id, "Missing session_id", ["session_id"])

        try:
            resolved_template = self._resolve_template_path(template_path)
        except FileNotFoundError:
            return self._record_failure(
                session_id,
                f"1040 template not found at {Path(template_path or self._settings.form_1040_template_path).expanduser()}",
                ["template_path"],
            )

        semantic_values = self._extract_semantic_values(tax_data)
        missing_required = [
            k for k in self.REQUIRED_SEMANTIC_FIELDS if not self._has_value(semantic_values.get(k))
        ]
        if missing_required:
            return self._record_failure(
                session_id,
                "Missing required taxpayer/tax fields for Form 1040.",
                missing_required,
                semantic_values=semantic_values,
            )

        try:
            from pypdf import PdfReader, PdfWriter
            from pypdf.generic import BooleanObject, NameObject
        except Exception:
            return self._record_failure(
                session_id,
                "pypdf is not installed. Add pypdf to requirements and install dependencies.",
                ["pypdf_dependency"],
                semantic_values=semantic_values,
            )

        reader = PdfReader(str(resolved_template))
        raw_fields = reader.get_fields() or {}
        if not raw_fields:
            return self._record_failure(
                session_id,
                "Template has no AcroForm fields. Provide a fillable 1040 template.",
                ["acroform_fields"],
                semantic_values=semantic_values,
            )

        template_field_names = list(raw_fields.keys())
        explicit_map = self._load_field_map()
        semantic_to_pdf_field = self._resolve_field_mapping(template_field_names, explicit_map)

        missing_pdf_targets = [
            k for k in self.REQUIRED_SEMANTIC_FIELDS if k in semantic_values and not semantic_to_pdf_field.get(k)
        ]
        if missing_pdf_targets:
            return self._record_failure(
                session_id,
                "Unable to map required semantic fields to PDF form fields. "
                "Add mappings in backend/forms/form1040_field_map.json.",
                missing_pdf_targets,
                semantic_values=semantic_values,
                template_fields=template_field_names[:40],
            )

        update_values: dict[str, str] = {}
        for key, value in semantic_values.items():
            if key == "filing_status":
                # Filing status uses checkboxes — handle separately below
                continue
            field_name = semantic_to_pdf_field.get(key)
            if field_name and self._has_value(value):
                update_values[field_name] = self._format_pdf_value(value)

        # Handle filing status checkbox: case-insensitive lookup
        filing_status_val = semantic_values.get("filing_status")
        if filing_status_val:
            status_str = str(filing_status_val).strip()
            checkbox_field = self.FILING_STATUS_CHECKBOXES.get(status_str)
            if not checkbox_field:
                status_lower = status_str.lower()
                for canonical, field in self.FILING_STATUS_CHECKBOXES.items():
                    if canonical.lower() == status_lower:
                        checkbox_field = field
                        break
            if checkbox_field:
                update_values[checkbox_field] = "/1"
            else:
                logger.warning(
                    "Filing status '%s' did not match any checkbox — skipping",
                    status_str,
                )

        try:
            writer = PdfWriter()
            writer.clone_document_from_reader(reader)
            for page in writer.pages:
                writer.update_page_form_field_values(page, update_values, auto_regenerate=False)

            try:
                if "/AcroForm" in writer._root_object:
                    writer._root_object["/AcroForm"].update(
                        {NameObject("/NeedAppearances"): BooleanObject(True)}
                    )
            except Exception as e:
                logger.warning("Could not set NeedAppearances: %s", e)

            output_path = FORM_OUTPUT_DIR / f"form1040_{session_id}.pdf"
            with output_path.open("wb") as f:
                writer.write(f)
        except OSError as exc:
            return self._record_failure(
                session_id,
                f"PDF write failed: {exc}",
                ["disk_write"],
                semantic_values=semantic_values,
            )
        except Exception as exc:
            return self._record_failure(
                session_id,
                f"PDF generation failed: {type(exc).__name__}: {exc}",
                ["pdf_generation"],
                semantic_values=semantic_values,
            )

        result = {
            "success": True,
            "session_id": session_id,
            "output_path": str(output_path.resolve()),
            "template_path": str(resolved_template.resolve()),
            "missing_required_fields": [],
            "fields_written_count": len(update_values),
            "fields_written": sorted(update_values.keys()),
        }
        _FORM_1040_STATUS[session_id] = result
        return result

    def _extract_semantic_values(self, tax_data: Dict[str, Any]) -> Dict[str, Any]:
        values: Dict[str, Any] = {}

        def pick(*keys: str):
            for key in keys:
                if key in tax_data and self._has_value(tax_data[key]):
                    return tax_data[key]
            return None

        values["first_name"] = pick("first_name", "taxpayer_first_name")
        values["last_name"] = pick("last_name", "taxpayer_last_name")
        values["ssn"] = pick("ssn", "taxpayer_ssn", "social_security_number")
        values["spouse_first_name"] = pick("spouse_first_name")
        values["spouse_last_name"] = pick("spouse_last_name")
        values["spouse_ssn"] = pick("spouse_ssn")
        values["address"] = pick("address", "street_address")
        values["city"] = pick("city")
        values["state"] = pick("state")
        values["zip"] = pick("zip", "zip_code", "postal_code")
        values["filing_status"] = pick("filing_status")
        values["tax_year"] = pick("tax_year")

        # Income line items
        values["wages"] = pick("wages", "w2_wages", "salaries", "wages_salaries_tips")

        total_income = pick("total_income")
        adjustments = pick("adjustments", "adjustments_to_income")
        adjusted_gross_income = pick("adjusted_gross_income", "agi")
        standard_deduction = pick("standard_deduction")
        total_deductions = pick("total_deductions")
        taxable_income = pick("taxable_income")
        tax = pick("tax", "tax_from_tables", "line16_tax")
        total_tax = pick("total_tax", "federal_tax", "estimated_tax_liability", "estimated_liability")
        federal_tax_withheld = pick("federal_tax_withheld", "withholding", "tax_withheld")

        values["total_income"] = total_income
        values["adjustments"] = adjustments
        values["adjusted_gross_income"] = adjusted_gross_income if adjusted_gross_income is not None else total_income
        values["standard_deduction"] = standard_deduction
        values["total_deductions"] = total_deductions
        values["taxable_income"] = taxable_income if taxable_income is not None else total_income
        values["tax"] = tax
        values["total_tax"] = total_tax
        values["federal_tax_withheld"] = federal_tax_withheld if federal_tax_withheld is not None else 0.0

        if self._is_number(values["total_tax"]) and self._is_number(values["federal_tax_withheld"]):
            delta = float(values["federal_tax_withheld"]) - float(values["total_tax"])
            values["refund_amount"] = max(delta, 0.0)
            values["amount_owed"] = abs(min(delta, 0.0))

        return {k: v for k, v in values.items() if self._has_value(v)}

    def _resolve_template_path(self, template_path: Optional[str] = None) -> Path:
        resolved_template = Path(template_path or self._settings.form_1040_template_path).expanduser()
        if not resolved_template.exists():
            raise FileNotFoundError(f"1040 template not found at {resolved_template}")
        return resolved_template

    def _resolve_field_mapping(
        self,
        template_fields: list[str],
        explicit_map: Dict[str, str],
    ) -> Dict[str, str]:
        resolved: Dict[str, str] = {}
        normalized_fields = {self._normalize(f): f for f in template_fields}

        for semantic, mapped in explicit_map.items():
            if semantic in self.FIELD_ALIASES and mapped in template_fields:
                resolved[semantic] = mapped

        for semantic, aliases in self.FIELD_ALIASES.items():
            if semantic in resolved:
                continue
            best_match = None
            for norm_name, original_name in normalized_fields.items():
                if any(alias in norm_name for alias in aliases):
                    best_match = original_name
                    break
            if best_match:
                resolved[semantic] = best_match

        return resolved

    def _load_field_map(self) -> Dict[str, str]:
        if not FIELD_MAP_PATH.exists():
            return {}
        try:
            data = json.loads(FIELD_MAP_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            logger.warning("Invalid form1040 field map file: %s", e)
        return {}

    def _record_failure(
        self,
        session_id: str,
        message: str,
        missing_fields: list[str],
        semantic_values: Optional[Dict[str, Any]] = None,
        template_fields: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        available_keys = sorted(semantic_values.keys()) if semantic_values else []
        result = {
            "success": False,
            "session_id": session_id,
            "error": message,
            "missing_required_fields": missing_fields,
            "available_semantic_keys": available_keys,
            "semantic_values": semantic_values or {},
            "template_fields_preview": template_fields or [],
            "output_path": None,
        }
        logger.warning(
            "Form 1040 generation failed for session %s: %s | missing=%s | available_keys=%s",
            session_id, message, missing_fields, available_keys,
        )
        if session_id:
            _FORM_1040_STATUS[session_id] = result
        return result

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    @staticmethod
    def _format_pdf_value(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    @staticmethod
    def _has_value(value: Any) -> bool:
        return value is not None and str(value).strip() != ""

    @staticmethod
    def _is_number(value: Any) -> bool:
        try:
            float(value)
            return True
        except Exception:
            return False
