"""S8.5 — _call_indianmedicinedb() tests.

20 tests covering: constant, signature, empty input, success, field mapping,
partial response, 404, 400, 500+retry, timeout, connect error, invalid JSON,
validation error, retry behavior, logging, httpx usage.
All HTTP calls mocked — no real network.
"""

from __future__ import annotations

import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.models.schemas import DrugInfo

MODULE = "backend.app.services.drug_lookup"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _api_response_json(
    brand_name: str = "Crocin",
    generic_name: str = "Paracetamol",
    therapeutic_class: str = "Analgesic",
    purpose: str = "Pain relief",
    side_effects: str = "Nausea",
    timing: str = "After meals",
    interactions: str = "None known",
) -> dict:
    """Build a dict matching the expected IndianMedicineDB API shape."""
    return {
        "brand_name": brand_name,
        "generic_name": generic_name,
        "therapeutic_class": therapeutic_class,
        "purpose": purpose,
        "side_effects": side_effects,
        "timing": timing,
        "interactions": interactions,
    }


def _mock_response(
    status_code: int = 200, json_data: dict | None = None, text: str = ""
) -> MagicMock:
    """Create a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    if json_data is not None:
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    else:
        resp.json.side_effect = json.JSONDecodeError("", "", 0)
        resp.text = text
    # raise_for_status behavior
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"{status_code}",
            request=MagicMock(spec=httpx.Request),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _mock_client(response: MagicMock | Exception):
    """Return an AsyncMock that behaves like httpx.AsyncClient context manager."""
    client_instance = AsyncMock()
    if isinstance(response, Exception):
        client_instance.get.side_effect = response
    else:
        client_instance.get.return_value = response
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_instance)
    client_cm.__aexit__ = AsyncMock(return_value=False)
    return client_cm, client_instance


# ── FR-1: constant ──────────────────────────────────────────────────────────


def test_indianmedicinedb_base_url_constant():
    from backend.app.services.drug_lookup import INDIANMEDICINEDB_BASE_URL

    assert isinstance(INDIANMEDICINEDB_BASE_URL, str)
    assert INDIANMEDICINEDB_BASE_URL.startswith("https://")
    assert not INDIANMEDICINEDB_BASE_URL.endswith("/")


# ── FR-2: signature ─────────────────────────────────────────────────────────


def test_call_indianmedicinedb_is_async():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    assert inspect.iscoroutinefunction(_call_indianmedicinedb)


def test_call_indianmedicinedb_signature():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    sig = inspect.signature(_call_indianmedicinedb)
    params = list(sig.parameters.keys())
    assert "medicine_name" in params
    assert "request_id" in params


# ── FR-2: empty name ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_empty_name():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    result = await _call_indianmedicinedb("", request_id="r1")
    assert result is None

    result2 = await _call_indianmedicinedb("   ", request_id="r2")
    assert result2 is None


# ── FR-2/FR-3: success + field mapping ───────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_success():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(200, _api_response_json())
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("Crocin", request_id="r1")

    assert result is not None
    assert isinstance(result, DrugInfo)
    assert result.brand_name == "Crocin"


@pytest.mark.asyncio
async def test_call_indianmedicinedb_field_mapping():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    data = _api_response_json(
        purpose="Fever reducer",
        side_effects="Drowsiness",
        timing="Before bed",
        interactions="Alcohol",
    )
    resp = _mock_response(200, data)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("Crocin")

    assert result.purpose_en == "Fever reducer"
    assert result.side_effects_en == "Drowsiness"
    assert result.timing_instructions == "Before bed"
    assert result.known_interactions == "Alcohol"


@pytest.mark.asyncio
async def test_call_indianmedicinedb_partial_response():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    data = {"brand_name": "Dolo"}  # minimal — all optional fields missing
    resp = _mock_response(200, data)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("Dolo")

    assert result is not None
    assert result.brand_name == "Dolo"
    assert result.generic_name is None
    assert result.purpose_en is None


# ── FR-4/FR-5: error handling ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_404_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(404)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("NotARealDrug")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_400_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(400)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("BadRequest")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_500_after_retries():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(500)
    cm, client_inst = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("ServerError")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_timeout_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    cm, _ = _mock_client(httpx.TimeoutException("timeout"))

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("SlowDrug")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_connect_error_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    cm, _ = _mock_client(httpx.ConnectError("refused"))

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("Offline")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_invalid_json_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(200, json_data=None, text="not json at all")
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("BadJSON")

    assert result is None


@pytest.mark.asyncio
async def test_call_indianmedicinedb_validation_error_returns_none():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    # Missing required brand_name → Pydantic validation error
    data = {"generic_name": "Something"}
    resp = _mock_response(200, data)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("Invalid")

    assert result is None


# ── FR-4: retry behavior ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_retry_on_5xx():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    fail_resp = _mock_response(500)
    ok_resp = _mock_response(200, _api_response_json(brand_name="Recovered"))

    client_instance = AsyncMock()
    client_instance.get.side_effect = [fail_resp, ok_resp]
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client_instance)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("RetryDrug")

    assert result is not None
    assert result.brand_name == "Recovered"
    assert client_instance.get.call_count == 2


@pytest.mark.asyncio
async def test_call_indianmedicinedb_no_retry_on_404():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(404)
    cm, client_inst = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        result = await _call_indianmedicinedb("NotFound")

    assert result is None
    client_inst.get.assert_called_once()


# ── FR-6: logging ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_logs_request_id():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(200, _api_response_json())
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        with patch(f"{MODULE}.logger") as mock_log:
            await _call_indianmedicinedb("Crocin", request_id="req-abc")

    all_args = " ".join(str(c) for c in mock_log.method_calls)
    assert "req-abc" in all_args


@pytest.mark.asyncio
async def test_call_indianmedicinedb_logs_success():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(200, _api_response_json())
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        with patch(f"{MODULE}.logger") as mock_log:
            await _call_indianmedicinedb("Crocin")

    # Should have at least one debug or info call
    assert mock_log.debug.called or mock_log.info.called


@pytest.mark.asyncio
async def test_call_indianmedicinedb_logs_not_found():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(404)
    cm, _ = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm):
        with patch(f"{MODULE}.logger") as mock_log:
            await _call_indianmedicinedb("Ghost")

    assert mock_log.debug.called or mock_log.warning.called


# ── FR-7: uses httpx ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_indianmedicinedb_uses_httpx():
    from backend.app.services.drug_lookup import _call_indianmedicinedb

    resp = _mock_response(200, _api_response_json())
    cm, client_inst = _mock_client(resp)

    with patch(f"{MODULE}.httpx.AsyncClient", return_value=cm) as mock_cls:
        await _call_indianmedicinedb("Crocin")

    mock_cls.assert_called_once()
    client_inst.get.assert_called_once()
