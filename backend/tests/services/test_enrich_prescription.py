"""S8.4 — enrich_prescription() tests.

20 tests covering: import, signature, empty input, single/multiple lookups,
positional alignment, concurrency via asyncio.gather, error resilience, logging.
All lookup_drug() calls are mocked — no real Redis needed.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import DrugInfo, MedicineEntry, PrescriptionData


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_drug(name: str = "Crocin") -> DrugInfo:
    return DrugInfo(brand_name=name, generic_name="Paracetamol", purpose_en="Pain relief")


def _make_prescription(*names: str) -> PrescriptionData:
    meds = [MedicineEntry(medicine_name=n, confidence=0.9) for n in names]
    return PrescriptionData(medicines=meds, overall_confidence=0.9)


MOCK_TARGET = "backend.app.services.drug_lookup.lookup_drug"


# ── FR-1: importable + signature ─────────────────────────────────────────────


def test_enrich_prescription_importable():
    from backend.app.services.drug_lookup import enrich_prescription  # noqa: F401

    assert callable(enrich_prescription)


def test_enrich_prescription_is_async():
    from backend.app.services.drug_lookup import enrich_prescription

    assert inspect.iscoroutinefunction(enrich_prescription)


def test_enrich_prescription_signature():
    from backend.app.services.drug_lookup import enrich_prescription

    sig = inspect.signature(enrich_prescription)
    params = list(sig.parameters.keys())
    assert "redis_client" in params
    assert "prescription" in params
    assert "request_id" in params


# ── FR-1 edge case: empty medicines ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_empty_medicines():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = PrescriptionData(medicines=[], overall_confidence=0.9)
    result = await enrich_prescription(AsyncMock(), rx)
    assert result == []


# ── FR-2/3: single medicine lookups ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_single_medicine_found():
    from backend.app.services.drug_lookup import enrich_prescription

    drug = _make_drug("Crocin")
    rx = _make_prescription("Crocin")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=drug):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 1
    assert result[0] is not None
    assert result[0].brand_name == "Crocin"


@pytest.mark.asyncio
async def test_enrich_prescription_single_medicine_not_found():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("UnknownDrug")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 1
    assert result[0] is None


# ── FR-2/3: multiple medicines ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_multiple_medicines_all_found():
    from backend.app.services.drug_lookup import enrich_prescription

    drugs = [_make_drug("A"), _make_drug("B"), _make_drug("C")]
    rx = _make_prescription("A", "B", "C")

    with patch(MOCK_TARGET, new_callable=AsyncMock, side_effect=drugs):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 3
    assert all(r is not None for r in result)


@pytest.mark.asyncio
async def test_enrich_prescription_multiple_medicines_mixed():
    from backend.app.services.drug_lookup import enrich_prescription

    side = [_make_drug("A"), None, _make_drug("C")]
    rx = _make_prescription("A", "B", "C")

    with patch(MOCK_TARGET, new_callable=AsyncMock, side_effect=side):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 3
    assert result[0] is not None
    assert result[1] is None
    assert result[2] is not None


@pytest.mark.asyncio
async def test_enrich_prescription_multiple_medicines_none_found():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("X", "Y", "Z")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 3
    assert all(r is None for r in result)


# ── FR-3: positional alignment ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_positional_alignment():
    from backend.app.services.drug_lookup import enrich_prescription

    drug_a = _make_drug("Alpha")
    drug_c = _make_drug("Charlie")
    side = [drug_a, None, drug_c]
    rx = _make_prescription("Alpha", "Bravo", "Charlie")

    with patch(MOCK_TARGET, new_callable=AsyncMock, side_effect=side):
        result = await enrich_prescription(AsyncMock(), rx)

    assert result[0].brand_name == "Alpha"
    assert result[1] is None
    assert result[2].brand_name == "Charlie"


# ── FR-2: concurrent gather ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_concurrent_gather():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("A", "B")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=_make_drug()):
        with patch("backend.app.services.drug_lookup.asyncio.gather", wraps=asyncio.gather) as m:
            await enrich_prescription(AsyncMock(), rx)
            m.assert_called_once()


# ── FR-1: passes redis_client and request_id ─────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_passes_request_id():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("Med1")
    mock_redis = AsyncMock()

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None) as m:
        await enrich_prescription(mock_redis, rx, request_id="req-42")

    m.assert_called_once()
    _, kwargs = m.call_args
    assert kwargs.get("request_id") == "req-42"


@pytest.mark.asyncio
async def test_enrich_prescription_passes_redis_client():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("Med1")
    mock_redis = AsyncMock()

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None) as m:
        await enrich_prescription(mock_redis, rx, request_id="req-1")

    args, _ = m.call_args
    assert args[0] is mock_redis


# ── FR-3: result length always matches input ─────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_result_length_matches_input():
    from backend.app.services.drug_lookup import enrich_prescription

    for n in (0, 1, 5):
        names = [f"Drug{i}" for i in range(n)]
        rx = _make_prescription(*names)
        with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None):
            result = await enrich_prescription(AsyncMock(), rx)
        assert len(result) == n


# ── FR-3: duplicate names ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_duplicate_names():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("Crocin", "Crocin")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=_make_drug("Crocin")) as m:
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 2
    assert m.call_count == 2


# ── FR-4: gather exception resilience ────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_gather_exception_resilience():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("A", "B")

    with patch(
        "backend.app.services.drug_lookup.asyncio.gather",
        side_effect=RuntimeError("boom"),
    ):
        result = await enrich_prescription(AsyncMock(), rx)

    assert len(result) == 2
    assert all(r is None for r in result)


# ── FR-5: logging ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_logs_start():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("A", "B")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=_make_drug()):
        with patch("backend.app.services.drug_lookup.logger") as mock_log:
            await enrich_prescription(AsyncMock(), rx, request_id="r1")

    # At least one log call should mention the count "2"
    all_args = " ".join(str(c) for c in mock_log.method_calls)
    assert "2" in all_args


@pytest.mark.asyncio
async def test_enrich_prescription_logs_completion():
    from backend.app.services.drug_lookup import enrich_prescription

    side = [_make_drug("A"), None]
    rx = _make_prescription("A", "B")

    with patch(MOCK_TARGET, new_callable=AsyncMock, side_effect=side):
        with patch("backend.app.services.drug_lookup.logger") as mock_log:
            await enrich_prescription(AsyncMock(), rx, request_id="r2")

    all_args = " ".join(str(c) for c in mock_log.method_calls)
    # Should mention hits and misses
    assert "1" in all_args  # 1 hit or 1 miss


@pytest.mark.asyncio
async def test_enrich_prescription_logs_request_id():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("A")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None):
        with patch("backend.app.services.drug_lookup.logger") as mock_log:
            await enrich_prescription(AsyncMock(), rx, request_id="req-xyz")

    all_args = " ".join(str(c) for c in mock_log.method_calls)
    assert "req-xyz" in all_args


# ── Return type ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prescription_returns_list_type():
    from backend.app.services.drug_lookup import enrich_prescription

    rx = _make_prescription("A")

    with patch(MOCK_TARGET, new_callable=AsyncMock, return_value=None):
        result = await enrich_prescription(AsyncMock(), rx)

    assert isinstance(result, list)
