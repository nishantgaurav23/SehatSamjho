"""S5.2 — Extraction Prompt tests.

Pure tests for EXTRACTION_SYSTEM_PROMPT, EXTRACTION_OUTPUT_SCHEMA,
and _build_extraction_prompt(). No mocking needed — all pure constants/functions.
"""

from __future__ import annotations

from backend.app.services.extraction import (
    EXTRACTION_OUTPUT_SCHEMA,
    EXTRACTION_SYSTEM_PROMPT,
    _build_extraction_prompt,
)


# ---------------------------------------------------------------------------
# EXTRACTION_SYSTEM_PROMPT tests
# ---------------------------------------------------------------------------


class TestExtractionSystemPrompt:
    """Tests for the EXTRACTION_SYSTEM_PROMPT constant."""

    def test_extraction_system_prompt_exists(self) -> None:
        """EXTRACTION_SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(EXTRACTION_SYSTEM_PROMPT, str)
        assert len(EXTRACTION_SYSTEM_PROMPT) > 0

    def test_extraction_system_prompt_has_persona(self) -> None:
        """Contains the 'medical document reader' persona (case-insensitive)."""
        assert "medical document reader" in EXTRACTION_SYSTEM_PROMPT.lower()

    def test_extraction_system_prompt_has_confidence_rule(self) -> None:
        """Mentions confidence scoring."""
        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "confidence" in lower

    def test_extraction_system_prompt_low_confidence_dosage_rule(self) -> None:
        """Instructs not to guess low-confidence dosages — leave as null."""
        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "null" in lower
        # Must mention not guessing when unclear
        assert any(kw in lower for kw in ("do not guess", "don't guess", "never guess", "leave"))

    def test_extraction_system_prompt_json_only(self) -> None:
        """Instructs JSON-only output, no markdown fences."""
        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "json" in lower
        assert any(kw in lower for kw in ("no markdown", "no code fences", "no fences"))

    def test_extraction_system_prompt_doc_type(self) -> None:
        """Mentions doc_type detection: prescription, lab_report, other."""
        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "doc_type" in lower
        assert "prescription" in lower
        assert "lab_report" in lower
        assert "other" in lower

    def test_extraction_system_prompt_no_phi_instruction(self) -> None:
        """Prompt instructs model not to invent patient details."""
        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert any(
            kw in lower
            for kw in ("do not invent", "don't invent", "do not fabricate", "never invent")
        )


# ---------------------------------------------------------------------------
# EXTRACTION_OUTPUT_SCHEMA tests
# ---------------------------------------------------------------------------


class TestExtractionOutputSchema:
    """Tests for the EXTRACTION_OUTPUT_SCHEMA constant."""

    def test_extraction_output_schema_exists(self) -> None:
        """EXTRACTION_OUTPUT_SCHEMA is a non-empty string."""
        assert isinstance(EXTRACTION_OUTPUT_SCHEMA, str)
        assert len(EXTRACTION_OUTPUT_SCHEMA) > 0

    def test_extraction_output_schema_has_prescription_fields(self) -> None:
        """Contains all PrescriptionData top-level field names."""
        for field in (
            "doctor_name",
            "patient_name",
            "date",
            "diagnosis",
            "medicines",
            "overall_confidence",
            "doc_type",
        ):
            assert field in EXTRACTION_OUTPUT_SCHEMA, f"Missing field: {field}"

    def test_extraction_output_schema_has_medicine_fields(self) -> None:
        """Contains all MedicineEntry field names."""
        for field in (
            "medicine_name",
            "dosage",
            "frequency",
            "duration",
            "instructions",
            "confidence",
        ):
            assert field in EXTRACTION_OUTPUT_SCHEMA, f"Missing field: {field}"

    def test_extraction_output_schema_confidence_range(self) -> None:
        """Schema mentions 0.0–1.0 range for confidence."""
        assert "0.0" in EXTRACTION_OUTPUT_SCHEMA
        assert "1.0" in EXTRACTION_OUTPUT_SCHEMA


# ---------------------------------------------------------------------------
# _build_extraction_prompt tests
# ---------------------------------------------------------------------------


class TestBuildExtractionPrompt:
    """Tests for _build_extraction_prompt()."""

    def test_build_extraction_prompt_returns_list(self) -> None:
        """Returns a list."""
        result = _build_extraction_prompt()
        assert isinstance(result, list)

    def test_build_extraction_prompt_single_system_message(self) -> None:
        """List has exactly one element with role=system."""
        result = _build_extraction_prompt()
        assert len(result) == 1
        assert result[0]["role"] == "system"

    def test_build_extraction_prompt_content_not_empty(self) -> None:
        """System message content is a non-empty string."""
        result = _build_extraction_prompt()
        content = result[0]["content"]
        assert isinstance(content, str)
        assert len(content) > 0

    def test_build_extraction_prompt_contains_persona(self) -> None:
        """Content includes the persona instruction."""
        result = _build_extraction_prompt()
        assert "medical document reader" in result[0]["content"].lower()

    def test_build_extraction_prompt_contains_schema(self) -> None:
        """Content includes all PrescriptionData field names."""
        result = _build_extraction_prompt()
        content = result[0]["content"]
        for field in (
            "doctor_name",
            "patient_name",
            "date",
            "diagnosis",
            "medicines",
            "overall_confidence",
            "doc_type",
        ):
            assert field in content, f"Missing field in prompt: {field}"

    def test_build_extraction_prompt_contains_low_confidence_rule(self) -> None:
        """Content includes the low-confidence instruction."""
        result = _build_extraction_prompt()
        lower = result[0]["content"].lower()
        assert any(kw in lower for kw in ("do not guess", "don't guess", "never guess", "leave"))

    def test_build_extraction_prompt_is_pure(self) -> None:
        """Calling twice returns equal results (deterministic)."""
        result1 = _build_extraction_prompt()
        result2 = _build_extraction_prompt()
        assert result1 == result2

    def test_build_extraction_prompt_no_side_effects(self) -> None:
        """Calling does not modify module state (_client stays unchanged)."""
        import backend.app.services.extraction as ext

        before = ext._client
        _build_extraction_prompt()
        after = ext._client
        assert before is after

    def test_build_extraction_prompt_message_structure(self) -> None:
        """Each message has exactly 'role' and 'content' keys."""
        result = _build_extraction_prompt()
        for msg in result:
            assert set(msg.keys()) == {"role", "content"}
