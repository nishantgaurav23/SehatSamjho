"""Tests for app/services/extraction.py

Tests GPT-4o Vision extraction with a mocked OpenAI client.
All tests are unit tests — no network calls, no external dependencies.

Run:
    cd backend
    pytest tests/services/test_extraction.py -v
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import DocumentType
from app.services.extraction import (
    ImageNotReadableError,
    NotMedicalDocumentError,
    _compute_confidence,
    _parse_to_pydantic,
    extract_prescription,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_prescription_json() -> dict:
    """Return a well-formed GPT-4o response for a typical prescription."""
    return {
        "is_medical_document": True,
        "is_legible": True,
        "doc_type": "prescription",
        "medications": [
            {
                "name": "Metformin",
                "dosage": "500mg",
                "frequency": "twice daily",
                "duration": "30 days",
                "quantity": "60 tablets",
                "instructions": "after food",
                "confidence": "high",
            }
        ],
        "diagnosis": "Type 2 Diabetes",
        "doctor_name": "Dr. Sharma",
        "date": "26/02/2026",
        "general_instructions": "Monitor blood sugar regularly",
        "warnings": ["Avoid alcohol"],
        "raw_text": "Metformin 500mg BD x 30 days",
        "overall_confidence": 0.9,
    }


def _mock_openai(mocker, json_response: dict) -> AsyncMock:
    """Patch _get_client() to return a mock AsyncOpenAI client.

    The mock's chat.completions.create is an AsyncMock that returns a
    response whose choices[0].message.content is json.dumps(json_response).
    """
    create_mock = AsyncMock()
    create_mock.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(json_response)))
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = create_mock
    mocker.patch("app.services.extraction._get_client", return_value=mock_client)
    return create_mock


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_extract_success(mocker):
    """Valid prescription JSON → returns PrescriptionData and confidence float."""
    _mock_openai(mocker, _valid_prescription_json())

    result, confidence = await extract_prescription(
        "http://img.example.com/rx.jpg", "SM_test_1"
    )

    assert len(result.medications) == 1
    assert result.medications[0].name == "Metformin"
    assert result.diagnosis == "Type 2 Diabetes"
    assert result.doc_type == DocumentType.PRESCRIPTION
    assert 0.0 <= confidence <= 1.0


async def test_extract_not_medical_document(mocker):
    """is_medical_document=false → raises NotMedicalDocumentError."""
    response = _valid_prescription_json()
    response["is_medical_document"] = False
    _mock_openai(mocker, response)

    with pytest.raises(NotMedicalDocumentError):
        await extract_prescription("http://img.example.com/food.jpg", "SM_test_2")


async def test_extract_unreadable_image(mocker):
    """is_legible=false → raises ImageNotReadableError."""
    response = _valid_prescription_json()
    response["is_legible"] = False
    response["overall_confidence"] = 0.3
    _mock_openai(mocker, response)

    with pytest.raises(ImageNotReadableError):
        await extract_prescription("http://img.example.com/blur.jpg", "SM_test_3")


async def test_extract_low_overall_confidence(mocker):
    """overall_confidence < 0.2 → raises ImageNotReadableError."""
    response = _valid_prescription_json()
    response["is_legible"] = True
    response["overall_confidence"] = 0.1
    _mock_openai(mocker, response)

    with pytest.raises(ImageNotReadableError):
        await extract_prescription("http://img.example.com/dark.jpg", "SM_test_4")


def test_parse_maps_doc_type():
    """doc_type="prescription" maps to DocumentType.PRESCRIPTION."""
    data = _valid_prescription_json()
    result = _parse_to_pydantic(data)
    assert result.doc_type == DocumentType.PRESCRIPTION


def test_parse_skips_empty_med_name():
    """Medications with empty names are excluded from the result."""
    data = _valid_prescription_json()
    # Append a medication with an empty name (GPT hallucination)
    data["medications"].append({"name": "", "dosage": "10mg", "confidence": "high"})

    result = _parse_to_pydantic(data)
    assert len(result.medications) == 1  # only Metformin survives
    assert result.medications[0].name == "Metformin"


def test_compute_confidence_all_high():
    """All high-confidence meds + overall=1.0 → confidence=1.0."""
    data = {
        "overall_confidence": 1.0,
        "medications": [
            {"name": "Metformin", "confidence": "high"},
            {"name": "Aspirin", "confidence": "high"},
        ],
    }
    result = _compute_confidence(data)
    # 0.6 * 1.0 + 0.4 * 1.0 = 1.0
    assert result == pytest.approx(1.0)


def test_compute_confidence_mixed():
    """Mixed med confidence + overall=0.8 → correct weighted average."""
    data = {
        "overall_confidence": 0.8,
        "medications": [
            {"name": "Metformin", "confidence": "high"},  # 1.0
            {"name": "Aspirin", "confidence": "low"},     # 0.5
        ],
    }
    result = _compute_confidence(data)
    # med_avg = (1.0 + 0.5) / 2 = 0.75
    # result = 0.6 * 0.8 + 0.4 * 0.75 = 0.48 + 0.30 = 0.78
    assert result == pytest.approx(0.78)
