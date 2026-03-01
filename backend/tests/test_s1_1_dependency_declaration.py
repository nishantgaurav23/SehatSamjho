"""Tests for Spec S1.1 — Dependency Declaration.

Validates pyproject.toml structure, dependencies, tool configuration,
and .env.example environment variable template.
"""

import importlib
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # repo root


# ── pyproject.toml existence & parsing ────────────────────────────────────────


def test_pyproject_exists():
    """pyproject.toml must exist at repo root."""
    assert (ROOT / "pyproject.toml").is_file()


def test_pyproject_valid_toml():
    """pyproject.toml must be valid TOML (parseable by tomllib)."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    assert "project" in data


# ── Runtime dependencies ──────────────────────────────────────────────────────

REQUIRED_RUNTIME_DEPS = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "asyncpg",
    "redis",
    "anthropic",
    "openai",
    "tenacity",
    "loguru",
    "httpx",
    "boto3",
    "pydantic-settings",
    "twilio",
    "python-multipart",
]


def test_runtime_deps_present():
    """All 14 runtime dependencies must be listed in [project.dependencies]."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    deps = data["project"]["dependencies"]
    # Normalize: lowercase, strip extras like [asyncio], strip version specifiers
    dep_names = []
    for d in deps:
        name = d.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip()
        dep_names.append(name.lower())

    for req in REQUIRED_RUNTIME_DEPS:
        assert req.lower() in dep_names, f"Missing runtime dependency: {req}"


# ── Dev extras ────────────────────────────────────────────────────────────────

REQUIRED_DEV_DEPS = ["pytest", "pytest-asyncio", "httpx", "ruff", "pytest-mock"]


def test_dev_extras_present():
    """All 5 dev dependencies must be in [project.optional-dependencies.dev]."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    dev_deps = data["project"]["optional-dependencies"]["dev"]
    dep_names = []
    for d in dev_deps:
        name = d.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip()
        dep_names.append(name.lower())

    for req in REQUIRED_DEV_DEPS:
        assert req.lower() in dep_names, f"Missing dev dependency: {req}"


# ── Project metadata ─────────────────────────────────────────────────────────


def test_python_version_constraint():
    """requires-python must be '>=3.11'."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    assert data["project"]["requires-python"] == ">=3.11"


# ── Tool configuration ───────────────────────────────────────────────────────


def test_ruff_line_length():
    """[tool.ruff] line-length must be 100."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    assert data["tool"]["ruff"]["line-length"] == 100


def test_pytest_asyncio_mode():
    """[tool.pytest.ini_options] asyncio_mode must be 'auto'."""
    text = (ROOT / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    assert data["tool"]["pytest"]["ini_options"]["asyncio_mode"] == "auto"


# ── .env.example ──────────────────────────────────────────────────────────────

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_FROM",
    "BHASHINI_API_KEY",
    "BHASHINI_USER_ID",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "S3_BUCKET",
    "DATABASE_URL",
    "REDIS_URL",
]


def test_env_example_exists():
    """.env.example must exist at repo root."""
    assert (ROOT / ".env.example").is_file()


def test_env_example_variables():
    """All 12 required environment variables must appear in .env.example."""
    content = (ROOT / ".env.example").read_text()
    for var in REQUIRED_ENV_VARS:
        assert var in content, f"Missing env variable in .env.example: {var}"


# ── Import validation ────────────────────────────────────────────────────────

IMPORTABLE_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "asyncpg",
    "redis",
    "anthropic",
    "openai",
    "tenacity",
    "loguru",
    "httpx",
    "boto3",
    "pydantic_settings",
    "twilio",
]


@pytest.mark.parametrize("package", IMPORTABLE_PACKAGES)
def test_imports_succeed(package):
    """All runtime packages must be importable."""
    importlib.import_module(package)
