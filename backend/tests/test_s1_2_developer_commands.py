"""Tests for S1.2 — Developer Commands (Makefile).

All tests are static file validation — parse the Makefile text and verify
targets, commands, .PHONY declarations, and tab indentation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Project root is two levels up from backend/tests/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MAKEFILE_PATH = PROJECT_ROOT / "Makefile"

EXPECTED_TARGETS = [
    "venv",
    "install",
    "install-dev",
    "local-dev",
    "local-test",
    "local-lint",
    "local-migrate",
    "seed",
    "dev",
    "test",
    "migrate",
]


@pytest.fixture(scope="module")
def makefile_text() -> str:
    """Read the Makefile once for all tests."""
    assert MAKEFILE_PATH.exists(), f"Makefile not found at {MAKEFILE_PATH}"
    return MAKEFILE_PATH.read_text()


def _get_target_block(makefile_text: str, target: str) -> str:
    """Extract the full recipe block for a given target (target line + indented lines)."""
    pattern = rf"^{re.escape(target)}\s*:.*$"
    match = re.search(pattern, makefile_text, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    # Collect subsequent lines that start with a tab (recipe lines)
    lines = makefile_text[start:].split("\n")
    block = [lines[0]]
    for line in lines[1:]:
        if line.startswith("\t"):
            block.append(line)
        elif line.strip() == "":
            continue  # skip blank lines within block
        else:
            break
    return "\n".join(block)


# ── Test 1: Makefile exists ──────────────────────────────────────────────────
def test_makefile_exists():
    assert MAKEFILE_PATH.exists(), f"Makefile should exist at {MAKEFILE_PATH}"


# ── Test 2: All 11 targets are defined ──────────────────────────────────────
def test_makefile_has_all_targets(makefile_text: str):
    for target in EXPECTED_TARGETS:
        pattern = rf"^{re.escape(target)}\s*:"
        assert re.search(pattern, makefile_text, re.MULTILINE), (
            f"Target '{target}' not found in Makefile"
        )


# ── Test 3: .PHONY declarations ─────────────────────────────────────────────
def test_makefile_phony_declarations(makefile_text: str):
    # Collect all targets listed after .PHONY:
    phony_matches = re.findall(r"^\.PHONY\s*:\s*(.+)$", makefile_text, re.MULTILINE)
    phony_targets = set()
    for match in phony_matches:
        phony_targets.update(match.split())
    for target in EXPECTED_TARGETS:
        assert target in phony_targets, f"Target '{target}' not declared as .PHONY"


# ── Test 4: venv target uses Python 3.11 ────────────────────────────────────
def test_makefile_venv_target_uses_python311(makefile_text: str):
    block = _get_target_block(makefile_text, "venv")
    assert block, "venv target block not found"
    assert "python3.11" in block or "python3" in block, (
        "venv target should reference python3.11 (or python3)"
    )
    assert "venv" in block.lower(), "venv target should create a virtual environment"


# ── Test 5: install target uses uv ──────────────────────────────────────────
def test_makefile_install_uses_uv(makefile_text: str):
    block = _get_target_block(makefile_text, "install")
    assert block, "install target block not found"
    assert "uv pip install" in block, "install target should use 'uv pip install'"


# ── Test 6: install-dev target uses uv ──────────────────────────────────────
def test_makefile_install_dev_uses_uv(makefile_text: str):
    block = _get_target_block(makefile_text, "install-dev")
    assert block, "install-dev target block not found"
    assert "uv pip install" in block, "install-dev target should use 'uv pip install'"
    assert "dev" in block, "install-dev target should reference the 'dev' extra"


# ── Test 7: local-dev target uses uvicorn ────────────────────────────────────
def test_makefile_local_dev_uses_uvicorn(makefile_text: str):
    block = _get_target_block(makefile_text, "local-dev")
    assert block, "local-dev target block not found"
    assert "uvicorn" in block, "local-dev target should run uvicorn"
    assert "--reload" in block, "local-dev target should use --reload flag"


# ── Test 8: local-test target uses pytest ────────────────────────────────────
def test_makefile_local_test_uses_pytest(makefile_text: str):
    block = _get_target_block(makefile_text, "local-test")
    assert block, "local-test target block not found"
    assert "pytest" in block, "local-test target should run pytest"
    assert "-v" in block, "local-test target should use -v flag"
    assert "--tb=short" in block, "local-test target should use --tb=short flag"


# ── Test 9: local-lint target uses ruff ──────────────────────────────────────
def test_makefile_local_lint_uses_ruff(makefile_text: str):
    block = _get_target_block(makefile_text, "local-lint")
    assert block, "local-lint target block not found"
    assert "ruff check" in block, "local-lint target should run 'ruff check'"
    assert "ruff format" in block, "local-lint target should run 'ruff format'"


# ── Test 10: local-migrate target uses alembic ───────────────────────────────
def test_makefile_local_migrate_uses_alembic(makefile_text: str):
    block = _get_target_block(makefile_text, "local-migrate")
    assert block, "local-migrate target block not found"
    assert "alembic upgrade head" in block, "local-migrate target should run 'alembic upgrade head'"


# ── Test 11: dev target uses docker compose ──────────────────────────────────
def test_makefile_dev_target_uses_docker_compose(makefile_text: str):
    block = _get_target_block(makefile_text, "dev")
    assert block, "dev target block not found"
    assert "docker compose up --build" in block or "docker-compose up --build" in block, (
        "dev target should run 'docker compose up --build'"
    )


# ── Test 12: test target uses docker ─────────────────────────────────────────
def test_makefile_test_target_uses_docker(makefile_text: str):
    block = _get_target_block(makefile_text, "test")
    assert block, "test target block not found"
    assert "docker" in block.lower(), "test target should use Docker"
    assert "pytest" in block, "test target should run pytest inside Docker"


# ── Test 13: migrate target uses docker ──────────────────────────────────────
def test_makefile_migrate_target_uses_docker(makefile_text: str):
    block = _get_target_block(makefile_text, "migrate")
    assert block, "migrate target block not found"
    assert "docker" in block.lower(), "migrate target should use Docker"
    assert "alembic" in block, "migrate target should run alembic inside Docker"


# ── Test 14: seed target defined ─────────────────────────────────────────────
def test_makefile_seed_target_defined(makefile_text: str):
    block = _get_target_block(makefile_text, "seed")
    assert block, "seed target block not found"
    assert "seed" in block.lower(), "seed target should reference a seed script or command"


# ── Test 15: Makefile uses tabs for recipe indentation ───────────────────────
def test_makefile_uses_tabs(makefile_text: str):
    lines = makefile_text.split("\n")
    for i, line in enumerate(lines, 1):
        # Recipe lines must start with a tab, not spaces
        # Skip blank lines, comments, variable assignments, .PHONY, and target definitions
        if line.strip() == "" or line.startswith("#") or line.startswith("."):
            continue
        if "=" in line and not line.startswith("\t"):
            continue  # variable assignment
        if re.match(r"^\S+\s*:", line):
            continue  # target definition line
        if line.startswith(" ") and not line.startswith("\t"):
            pytest.fail(f"Line {i} uses spaces instead of tab for recipe indentation: {line!r}")
