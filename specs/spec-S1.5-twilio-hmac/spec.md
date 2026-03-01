# Spec S1.5 — Twilio HMAC Verification

## Overview
Implements `validate_twilio_signature(request, token)` in `backend/app/core/security.py`. This function validates the `X-Twilio-Signature` header on incoming webhook requests using Twilio's HMAC-SHA1 algorithm, rejecting forged requests with HTTP 403. It is used as a FastAPI dependency on the webhook endpoint to ensure only authentic Twilio requests are processed.

## Dependencies
- **S1.3** (pydantic-settings config) — requires `TWILIO_AUTH_TOKEN` from `Settings`

## Target Location
- `backend/app/core/security.py`

---

## Functional Requirements

### FR-1: Twilio request validator setup
- **What**: Create a Twilio `RequestValidator` instance using `settings.TWILIO_AUTH_TOKEN`
- **Inputs**: `TWILIO_AUTH_TOKEN` from config
- **Outputs**: A `RequestValidator` object capable of validating HMAC-SHA1 signatures
- **Edge cases**: Missing or empty auth token (should fail at config level via S1.3)

### FR-2: Signature validation function
- **What**: `validate_twilio_signature(request: Request)` — an async function that extracts the `X-Twilio-Signature` header, reconstructs the request URL and form body, and calls `RequestValidator.validate()` to verify authenticity
- **Inputs**: FastAPI `Request` object (contains headers, URL, form data)
- **Outputs**: Returns `None` on success (pass-through dependency). Raises `HTTPException(status_code=403)` on failure
- **Edge cases**:
  - Missing `X-Twilio-Signature` header → 403
  - Invalid/tampered signature → 403
  - Empty form body (still valid if signature matches) → pass
  - GET requests or non-form content types → handle gracefully

### FR-3: FastAPI dependency integration
- **What**: Export `validate_twilio_signature` as a reusable FastAPI `Depends()` dependency that can be attached to webhook routes
- **Inputs**: Injected by FastAPI's dependency injection system
- **Outputs**: No return value on success; blocks request pipeline with 403 on failure
- **Edge cases**: Dependency must be async-compatible (async def)

### FR-4: URL reconstruction
- **What**: Reconstruct the full request URL as Twilio sees it (scheme + host + path). Must handle reverse proxies where `X-Forwarded-Proto` and `X-Forwarded-Host` headers may be present
- **Inputs**: `request.url`, `request.headers`
- **Outputs**: Full URL string used for HMAC computation
- **Edge cases**:
  - Behind a reverse proxy (nginx/ALB): use `X-Forwarded-Proto` for scheme, `X-Forwarded-Host` for host
  - Direct connection (no proxy headers): use `request.url` as-is

---

## Tangible Outcomes

- [ ] **Outcome 1**: `backend/app/core/security.py` exists with `validate_twilio_signature` function
- [ ] **Outcome 2**: Valid Twilio signatures pass through without error
- [ ] **Outcome 3**: Invalid/missing signatures raise HTTP 403 with `{"detail": "Invalid Twilio signature"}`
- [ ] **Outcome 4**: Function works as a FastAPI `Depends()` dependency
- [ ] **Outcome 5**: URL reconstruction handles both direct and proxied requests
- [ ] **Outcome 6**: All tests pass (`backend/tests/core/test_security.py`)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_valid_signature_passes**: Construct a request with a valid HMAC signature → function returns None (no exception)
2. **test_invalid_signature_returns_403**: Construct a request with a wrong signature → HTTPException 403 raised
3. **test_missing_signature_header_returns_403**: Request with no `X-Twilio-Signature` header → HTTPException 403 raised
4. **test_empty_signature_returns_403**: Request with empty string signature → HTTPException 403 raised
5. **test_uses_twilio_auth_token_from_settings**: Verify the validator is initialized with `settings.TWILIO_AUTH_TOKEN`
6. **test_form_body_included_in_validation**: Ensure form POST parameters are passed to `RequestValidator.validate()` (Twilio includes sorted form params in HMAC computation)
7. **test_url_reconstruction_direct**: Direct request (no proxy headers) → URL matches `request.url`
8. **test_url_reconstruction_behind_proxy**: Request with `X-Forwarded-Proto: https` and `X-Forwarded-Host: example.com` → URL uses forwarded values
9. **test_dependency_is_async**: `validate_twilio_signature` is an async function (coroutine)
10. **test_valid_signature_with_empty_body**: POST with no form fields but valid signature → passes

### Mocking Strategy
- Mock `twilio.request_validator.RequestValidator.validate` to control return value (True/False)
- Mock `settings.TWILIO_AUTH_TOKEN` via environment variable override or monkeypatch
- Use `httpx.AsyncClient` with `ASGITransport` or construct mock `Request` objects directly

### Coverage Expectation
- All public functions have at least one test; edge cases (missing header, proxy, empty body) covered
- 10 tests total

---

## References
- roadmap.md — S1.5 row
- [Twilio Request Validation docs](https://www.twilio.com/docs/usage/security#validating-requests)
- `twilio.request_validator.RequestValidator` from the `twilio` Python package
- design.md, requirements.md
