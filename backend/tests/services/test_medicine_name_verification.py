"""Medicine Name Verification — Tests for the 4-layer correction pipeline.

20 tests covering:
- L1: Extraction prompt has handwriting disambiguation instructions
- L2: Fuzzy matching (_fuzzy_match_drug_name, _brand_name_cache)
- L3: Translation prompt includes unverified name warnings
- L4: name_verified field on MedicineEntry + enrich_prescription sets it
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import DrugInfo, MedicineEntry, PrescriptionData


# ── Sample fixtures ──────────────────────────────────────────────────────────

SAMPLE_DRUG = DrugInfo(
    brand_name="Depraven",
    generic_name="Venlafaxine",
    therapeutic_class="antidepressant",
    purpose_en="Treats depression and anxiety",
    side_effects_en="Nausea, dizziness",
    timing_instructions="After meals",
    known_interactions="MAO inhibitors",
)

SAMPLE_DRUG_JSON = SAMPLE_DRUG.model_dump_json()


# ══════════════════════════════════════════════════════════════════════════════
# L1: Extraction prompt tests
# ══════════════════════════════════════════════════════════════════════════════


class TestL1ExtractionPrompt:
    def test_prompt_has_handwriting_disambiguation(self):
        from backend.app.services.extraction import EXTRACTION_SYSTEM_PROMPT

        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "disambiguation" in lower or "ambiguous" in lower

    def test_prompt_mentions_letter_confusions(self):
        from backend.app.services.extraction import EXTRACTION_SYSTEM_PROMPT

        # Must mention common letter confusions
        assert "D" in EXTRACTION_SYSTEM_PROMPT and "R" in EXTRACTION_SYSTEM_PROMPT

    def test_prompt_uses_doctor_specialization(self):
        from backend.app.services.extraction import EXTRACTION_SYSTEM_PROMPT

        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "specializ" in lower or "specialty" in lower or "specialisation" in lower

    def test_prompt_uses_letterhead_context(self):
        from backend.app.services.extraction import EXTRACTION_SYSTEM_PROMPT

        lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "letterhead" in lower or "hospital" in lower


# ══════════════════════════════════════════════════════════════════════════════
# L2: Fuzzy matching tests
# ══════════════════════════════════════════════════════════════════════════════


class TestL2FuzzyMatching:
    def test_fuzzy_match_function_importable(self):
        from backend.app.services.drug_lookup import _fuzzy_match_drug_name

        assert callable(_fuzzy_match_drug_name)

    def test_brand_name_cache_exists(self):
        from backend.app.services.drug_lookup import _brand_name_cache

        assert isinstance(_brand_name_cache, set)

    def test_fuzzy_match_empty_cache_returns_none(self):
        from backend.app.services.drug_lookup import _brand_name_cache, _fuzzy_match_drug_name

        # Temporarily clear cache
        original = _brand_name_cache.copy()
        _brand_name_cache.clear()
        try:
            assert _fuzzy_match_drug_name("depraven") is None
        finally:
            _brand_name_cache.update(original)

    def test_fuzzy_match_finds_close_match(self):
        from backend.app.services.drug_lookup import _brand_name_cache, _fuzzy_match_drug_name

        original = _brand_name_cache.copy()
        _brand_name_cache.clear()
        _brand_name_cache.add("depraven")
        _brand_name_cache.add("metformin")
        try:
            # "repraven" is 1 edit away from "depraven"
            result = _fuzzy_match_drug_name("repraven")
            assert result == "depraven"
        finally:
            _brand_name_cache.clear()
            _brand_name_cache.update(original)

    def test_fuzzy_match_rejects_distant_name(self):
        from backend.app.services.drug_lookup import _brand_name_cache, _fuzzy_match_drug_name

        original = _brand_name_cache.copy()
        _brand_name_cache.clear()
        _brand_name_cache.add("depraven")
        try:
            # "zzzzzzz" is too far from anything
            result = _fuzzy_match_drug_name("zzzzzzz")
            assert result is None
        finally:
            _brand_name_cache.clear()
            _brand_name_cache.update(original)

    def test_fuzzy_match_empty_name_returns_none(self):
        from backend.app.services.drug_lookup import _fuzzy_match_drug_name

        assert _fuzzy_match_drug_name("") is None

    @pytest.mark.asyncio
    async def test_lookup_drug_uses_fuzzy_fallback(self):
        """When exact match misses but fuzzy finds 'depraven', return its DrugInfo."""
        from backend.app.services.drug_lookup import _brand_name_cache, lookup_drug

        original = _brand_name_cache.copy()
        _brand_name_cache.clear()
        _brand_name_cache.add("depraven")

        mock_redis = AsyncMock()

        async def mock_get(key):
            if key == "drug:depraven":
                return SAMPLE_DRUG_JSON  # fuzzy target exists
            return None  # everything else misses

        mock_redis.get = AsyncMock(side_effect=mock_get)

        try:
            result = await lookup_drug(mock_redis, "Repraven", request_id="req-fuzzy")
            assert result is not None
            assert result.brand_name == "Depraven"
        finally:
            _brand_name_cache.clear()
            _brand_name_cache.update(original)


# ══════════════════════════════════════════════════════════════════════════════
# L3: Translation prompt verification tests
# ══════════════════════════════════════════════════════════════════════════════


class TestL3TranslationPrompt:
    def test_unverified_names_in_user_prompt(self):
        from backend.app.services.translation import _build_user_prompt

        prescription = PrescriptionData(
            medicines=[
                MedicineEntry(medicine_name="Repraven", confidence=0.9),
                MedicineEntry(medicine_name="Telpres AM", confidence=0.9),
            ],
            overall_confidence=0.85,
        )
        # Only Telpres AM has drug info, Repraven does not
        drug_info_list = [None, SAMPLE_DRUG]

        prompt = _build_user_prompt(prescription, "Hindi", "hi", drug_info_list)

        assert "[UNVERIFIED]" in prompt
        assert "Repraven" in prompt
        assert "Name Verification Warning" in prompt

    def test_no_unverified_section_when_all_verified(self):
        from backend.app.services.translation import _build_user_prompt

        prescription = PrescriptionData(
            medicines=[
                MedicineEntry(medicine_name="Depraven", confidence=0.9),
            ],
            overall_confidence=0.85,
        )
        drug_info_list = [SAMPLE_DRUG]

        prompt = _build_user_prompt(prescription, "Hindi", "hi", drug_info_list)

        assert "[UNVERIFIED]" not in prompt
        assert "Name Verification Warning" not in prompt

    def test_unverified_with_no_drug_info_list(self):
        from backend.app.services.translation import _build_user_prompt

        prescription = PrescriptionData(
            medicines=[
                MedicineEntry(medicine_name="UnknownDrug", confidence=0.9),
            ],
            overall_confidence=0.85,
        )

        prompt = _build_user_prompt(prescription, "Hindi", "hi", drug_info_list=None)

        # No drug_info_list at all → all medicines unverified
        assert "[UNVERIFIED]" in prompt
        assert "UnknownDrug" in prompt


# ══════════════════════════════════════════════════════════════════════════════
# L4: name_verified field tests
# ══════════════════════════════════════════════════════════════════════════════


class TestL4NameVerified:
    def test_medicine_entry_has_name_verified_field(self):
        med = MedicineEntry(medicine_name="Test", confidence=0.9)
        assert hasattr(med, "name_verified")
        assert med.name_verified is True  # default

    def test_name_verified_defaults_to_true(self):
        med = MedicineEntry(medicine_name="Paracetamol", confidence=0.9)
        assert med.name_verified is True

    def test_name_verified_can_be_set_false(self):
        med = MedicineEntry(medicine_name="Unknown", confidence=0.9, name_verified=False)
        assert med.name_verified is False

    @pytest.mark.asyncio
    async def test_enrich_prescription_sets_name_verified_false(self):
        from backend.app.services.drug_lookup import enrich_prescription

        prescription = PrescriptionData(
            medicines=[
                MedicineEntry(medicine_name="Depraven", confidence=0.9),
                MedicineEntry(medicine_name="UnknownXYZ", confidence=0.9),
            ],
            overall_confidence=0.85,
        )

        mock_redis = AsyncMock()

        async def mock_get(key):
            if "depraven" in key:
                return SAMPLE_DRUG_JSON
            return None

        mock_redis.get = AsyncMock(side_effect=mock_get)

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            return_value=None,
        ):
            results = await enrich_prescription(mock_redis, prescription)

        # Depraven found → name_verified stays True
        assert prescription.medicines[0].name_verified is True
        # UnknownXYZ not found → name_verified set to False
        assert prescription.medicines[1].name_verified is False

    @pytest.mark.asyncio
    async def test_enrich_prescription_all_verified(self):
        from backend.app.services.drug_lookup import enrich_prescription

        prescription = PrescriptionData(
            medicines=[
                MedicineEntry(medicine_name="Depraven", confidence=0.9),
            ],
            overall_confidence=0.85,
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=SAMPLE_DRUG_JSON)

        results = await enrich_prescription(mock_redis, prescription)

        assert prescription.medicines[0].name_verified is True
