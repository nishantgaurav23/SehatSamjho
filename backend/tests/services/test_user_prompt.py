"""Tests for S7.3 — User Prompt Builder (_build_user_prompt).

Pure-function tests — no mocking needed. All tests operate on Pydantic models
and verify string output structure.
"""

from __future__ import annotations

import inspect

import pytest

from backend.app.models.schemas import DrugInfo, MedicineEntry, PrescriptionData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_prescription() -> PrescriptionData:
    """Prescription with all fields populated."""
    return PrescriptionData(
        doctor_name="Dr. Sharma",
        patient_name="Rahul Kumar",  # must NOT appear in output
        date="2024-12-01",
        diagnosis="Type 2 Diabetes",
        medicines=[
            MedicineEntry(
                medicine_name="Metformin",
                dosage="500mg",
                frequency="twice daily",
                duration="30 days",
                instructions="after meals",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Glimepiride",
                dosage="1mg",
                frequency="once daily",
                duration="30 days",
                instructions="before breakfast",
                confidence=0.55,
            ),
        ],
        overall_confidence=0.85,
    )


@pytest.fixture()
def minimal_prescription() -> PrescriptionData:
    """Prescription with all optional fields as None and empty medicines."""
    return PrescriptionData(
        doctor_name=None,
        patient_name=None,
        date=None,
        diagnosis=None,
        medicines=[],
        overall_confidence=0.6,
    )


@pytest.fixture()
def sample_drug_info_list() -> list[DrugInfo]:
    """Two DrugInfo entries for enrichment."""
    return [
        DrugInfo(
            brand_name="Metformin",
            generic_name="Metformin Hydrochloride",
            therapeutic_class="Anti-diabetic",
            purpose_en="Controls blood sugar levels",
            side_effects_en="Nausea, diarrhea",
            timing_instructions="Take after meals",
            known_interactions="Alcohol may increase lactic acidosis risk",
        ),
        DrugInfo(
            brand_name="Glimepiride",
            generic_name="Glimepiride",
            therapeutic_class="Sulfonylurea",
            purpose_en="Stimulates insulin release",
            side_effects_en="Hypoglycemia",
            timing_instructions="Take before breakfast",
            known_interactions=None,
        ),
    ]


# ---------------------------------------------------------------------------
# Test 1: Import and callable
# ---------------------------------------------------------------------------


class TestImportAndSignature:
    """FR-1: _build_user_prompt exists and has correct signature."""

    def test_import_and_callable(self) -> None:
        from backend.app.services.translation import _build_user_prompt

        assert callable(_build_user_prompt)

    def test_signature_params(self) -> None:
        from backend.app.services.translation import _build_user_prompt

        sig = inspect.signature(_build_user_prompt)
        params = list(sig.parameters.keys())
        assert "prescription" in params
        assert "language_name" in params
        assert "language_code" in params
        assert "drug_info_list" in params

    def test_returns_string(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 4-5: Language header
# ---------------------------------------------------------------------------


class TestLanguageHeader:
    """FR-2: Language target directive at the top."""

    def test_language_header_present(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert result.startswith("Translate the following prescription into")

    def test_language_header_contains_name_and_code(
        self, full_prescription: PrescriptionData
    ) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Tamil", "ta")
        first_line = result.split("\n")[0]
        assert "Tamil" in first_line
        assert "ta" in first_line


# ---------------------------------------------------------------------------
# Test 6-8: Prescription metadata
# ---------------------------------------------------------------------------


class TestPrescriptionMetadata:
    """FR-3: Prescription details section."""

    def test_prescription_metadata_present(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert "Dr. Sharma" in result
        assert "2024-12-01" in result
        assert "Type 2 Diabetes" in result
        assert "0.85" in result

    def test_patient_name_excluded(self, full_prescription: PrescriptionData) -> None:
        """FR-7: PHI protection — patient_name must never appear."""
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert "Rahul Kumar" not in result
        assert "patient_name" not in result.lower()

    def test_none_metadata_shows_not_specified(
        self, minimal_prescription: PrescriptionData
    ) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(minimal_prescription, "Hindi", "hi")
        assert result.count("Not specified") >= 3  # doctor, date, diagnosis


# ---------------------------------------------------------------------------
# Test 9-12: Medicine entries
# ---------------------------------------------------------------------------


class TestMedicineEntries:
    """FR-4: Medicine serialization with confidence marking."""

    def test_medicine_entry_serialized(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert "Metformin" in result
        assert "500mg" in result
        assert "twice daily" in result
        assert "30 days" in result
        assert "after meals" in result
        assert "0.95" in result

    def test_multiple_medicines_numbered(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert "Medicine 1" in result
        assert "Medicine 2" in result

    def test_low_confidence_medicine_marked(self, full_prescription: PrescriptionData) -> None:
        """Confidence < 0.7 triggers [LOW CONFIDENCE] marker."""
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        # Glimepiride has confidence 0.55
        glim_idx = result.index("Glimepiride")
        # Find the header line containing Glimepiride
        before_glim = result[:glim_idx]
        last_newline = before_glim.rfind("\n")
        header_line = result[last_newline : glim_idx + len("Glimepiride")]
        assert "[LOW CONFIDENCE]" in header_line

    def test_high_confidence_medicine_not_marked(self, full_prescription: PrescriptionData) -> None:
        """Confidence >= 0.7 should NOT have [LOW CONFIDENCE] marker."""
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        # Find the header line for Medicine 1 (Metformin, confidence=0.95)
        for line in result.split("\n"):
            if "Medicine 1" in line:
                assert "[LOW CONFIDENCE]" not in line
                break


# ---------------------------------------------------------------------------
# Test 13-16: Drug enrichment
# ---------------------------------------------------------------------------


class TestDrugEnrichment:
    """FR-5: Drug information section."""

    def test_drug_info_section_present(
        self,
        full_prescription: PrescriptionData,
        sample_drug_info_list: list[DrugInfo],
    ) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(
            full_prescription, "Hindi", "hi", drug_info_list=sample_drug_info_list
        )
        assert "## Drug Information" in result

    def test_drug_info_fields_present(
        self,
        full_prescription: PrescriptionData,
        sample_drug_info_list: list[DrugInfo],
    ) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(
            full_prescription, "Hindi", "hi", drug_info_list=sample_drug_info_list
        )
        assert "Metformin Hydrochloride" in result
        assert "Anti-diabetic" in result
        assert "Controls blood sugar levels" in result
        assert "Nausea, diarrhea" in result
        assert "Take after meals" in result
        assert "Alcohol may increase lactic acidosis risk" in result

    def test_drug_info_none_omitted(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi", drug_info_list=None)
        assert "## Drug Information" not in result

    def test_drug_info_empty_list_omitted(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi", drug_info_list=[])
        assert "## Drug Information" not in result


# ---------------------------------------------------------------------------
# Test 17-18: Glossary section
# ---------------------------------------------------------------------------


class TestGlossarySection:
    """FR-6: Glossary context is injected via system prompt only (not user prompt)."""

    def test_glossary_not_in_user_prompt(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert "## Glossary Reference" not in result


# ---------------------------------------------------------------------------
# Test 19-20: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and purity."""

    def test_empty_medicines_list(self, minimal_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result = _build_user_prompt(minimal_prescription, "Hindi", "hi")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should still have language header and prescription details
        assert "Translate the following prescription into" in result
        assert "## Prescription Details" in result
        # No medicine entries
        assert "Medicine 1" not in result

    def test_pure_function_no_side_effects(self, full_prescription: PrescriptionData) -> None:
        from backend.app.services.translation import _build_user_prompt

        result1 = _build_user_prompt(full_prescription, "Hindi", "hi")
        result2 = _build_user_prompt(full_prescription, "Hindi", "hi")
        assert result1 == result2
