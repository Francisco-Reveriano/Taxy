from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class TaxDocumentType(str, Enum):
    W2 = "W-2"
    FORM_1099_NEC = "1099-NEC"
    FORM_1099_MISC = "1099-MISC"
    FORM_1099_INT = "1099-INT"
    FORM_1099_DIV = "1099-DIV"
    FORM_1099_B = "1099-B"
    FORM_1040 = "1040"
    SCHEDULE_A = "Schedule A"
    SCHEDULE_B = "Schedule B"
    SCHEDULE_C = "Schedule C"
    SCHEDULE_D = "Schedule D"
    FORM_1098 = "1098"
    UNKNOWN = "Unknown"


class OCRField(BaseModel):
    field_name: str
    field_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: Optional[dict] = None
    page_number: int = 1
    is_corrected: bool = False
    original_value: Optional[str] = None


class TaxDocument(BaseModel):
    file_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str
    document_type: TaxDocumentType = TaxDocumentType.UNKNOWN
    sha256_hash: str
    file_path: str
    fields: List[OCRField] = []
    ocr_completed: bool = False
    upload_timestamp: str = ""
    session_id: str = ""

    def get_field(self, name: str) -> Optional[OCRField]:
        for f in self.fields:
            if f.field_name == name:
                return f
        return None
