import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import forms


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(forms.router, prefix="/api")
    return TestClient(app)


def test_get_form_1040_template_fields_success_and_safe_payload(client: TestClient, monkeypatch):
    payload = {
        "template_file": "f1040.pdf",
        "field_count": 2,
        "fields": [
            {
                "index": 0,
                "name": "topmostSubform[0].Page1[0].f1_01[0]",
                "normalized_name": "topmostsubform0page10f1010",
                "pdf_type": "/Tx",
                "mapped_semantic_keys": ["first_name"],
            },
            {
                "index": 1,
                "name": "topmostSubform[0].Page1[0].f1_02[0]",
                "normalized_name": "topmostsubform0page10f1020",
                "pdf_type": "/Tx",
                "mapped_semantic_keys": ["last_name"],
            },
        ],
        "semantic_mapping": {
            "required_semantic_fields": ["first_name", "last_name", "ssn"],
            "required_missing_mapping": ["ssn"],
            "resolved_semantic_to_pdf_field": {
                "first_name": "topmostSubform[0].Page1[0].f1_01[0]",
                "last_name": "topmostSubform[0].Page1[0].f1_02[0]",
            },
            "explicit_map_keys": [],
        },
    }

    monkeypatch.setattr(forms.form1040_tool, "introspect_template_fields", lambda: payload)
    response = client.get("/api/forms/1040/template-fields")

    assert response.status_code == 200
    data = response.json()
    assert data["template_file"] == "f1040.pdf"
    assert data["field_count"] == 2
    assert len(data["fields"]) == 2
    assert "output_path" not in data
    assert "template_path" not in data


def test_get_form_1040_template_fields_not_found_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def _raise_not_found():
        raise FileNotFoundError("1040 template not found at /secret/path/f1040.pdf")

    monkeypatch.setattr(forms.form1040_tool, "introspect_template_fields", _raise_not_found)
    response = client.get("/api/forms/1040/template-fields")

    assert response.status_code == 404
    assert "1040 template not found" in response.json()["detail"]


def test_get_form_1040_template_fields_invalid_template_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def _raise_no_fields():
        raise ValueError("Template has no AcroForm fields. Provide a fillable 1040 template.")

    monkeypatch.setattr(forms.form1040_tool, "introspect_template_fields", _raise_no_fields)
    response = client.get("/api/forms/1040/template-fields")

    assert response.status_code == 422
    assert "AcroForm fields" in response.json()["detail"]
