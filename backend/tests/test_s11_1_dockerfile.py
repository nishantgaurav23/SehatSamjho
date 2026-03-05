"""
Tests for S11.1 — Multi-stage Dockerfile.

Static file validation tests — parse Dockerfile text directly.
No mocking needed (same pattern as S1.1, S1.2, S2.5).
"""

import re
from pathlib import Path

import pytest

DOCKERFILE_PATH = Path(__file__).resolve().parents[2] / "backend" / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_content() -> str:
    """Read the Dockerfile content once for all tests."""
    assert DOCKERFILE_PATH.exists(), f"Dockerfile not found at {DOCKERFILE_PATH}"
    return DOCKERFILE_PATH.read_text()


@pytest.fixture(scope="module")
def dockerfile_lines(dockerfile_content: str) -> list[str]:
    """Split Dockerfile into non-empty, non-comment lines."""
    return [
        line.strip()
        for line in dockerfile_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# Helper: split Dockerfile into stages
# ---------------------------------------------------------------------------
def _split_stages(content: str) -> dict[str, str]:
    """Split Dockerfile content into named stages (text between FROM ... AS <name> blocks)."""
    pattern = r"FROM\s+\S+\s+AS\s+(\w+)"
    matches = list(re.finditer(pattern, content, re.IGNORECASE))
    stages: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).lower()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        stages[name] = content[start:end]
    return stages


# ===== Test 1: Dockerfile exists =====
class TestDockerfileExists:
    def test_dockerfile_exists(self):
        assert DOCKERFILE_PATH.exists(), "backend/Dockerfile must exist"

    def test_dockerfile_is_file(self):
        assert DOCKERFILE_PATH.is_file(), "backend/Dockerfile must be a regular file"


# ===== Test 2: Valid syntax =====
class TestDockerfileValidSyntax:
    def test_starts_with_from(self, dockerfile_lines: list[str]):
        assert dockerfile_lines[0].upper().startswith("FROM"), "Dockerfile must start with FROM"

    def test_no_empty_file(self, dockerfile_content: str):
        assert len(dockerfile_content.strip()) > 0, "Dockerfile must not be empty"


# ===== Test 3: Three named stages =====
class TestThreeNamedStages:
    def test_exactly_three_from_as(self, dockerfile_content: str):
        stages = re.findall(r"FROM\s+\S+\s+AS\s+\w+", dockerfile_content, re.IGNORECASE)
        assert len(stages) == 3, f"Expected 3 named stages, found {len(stages)}: {stages}"

    def test_stage_names(self, dockerfile_content: str):
        names = re.findall(r"FROM\s+\S+\s+AS\s+(\w+)", dockerfile_content, re.IGNORECASE)
        names_lower = [n.lower() for n in names]
        assert names_lower == [
            "base",
            "dev",
            "prod",
        ], f"Expected stages [base, dev, prod], got {names_lower}"


# ===== Test 4: Base stage uses python:3.11-slim =====
class TestBaseStage:
    def test_base_python_311_slim(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert re.search(r"FROM\s+python:3\.11-slim", base, re.IGNORECASE), (
            "Base stage must use python:3.11-slim"
        )

    def test_base_installs_uv(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert "uv" in base.lower(), "Base stage must install uv"

    def test_base_copies_pyproject_before_source(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        pyproject_pos = base.lower().find("copy pyproject.toml")
        # pyproject.toml should be copied in base, before any COPY backend/
        assert pyproject_pos >= 0, "Base stage must COPY pyproject.toml"

    def test_base_uv_pip_install_system(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert re.search(r"uv\s+pip\s+install\s+--system", base), (
            "Base stage must run 'uv pip install --system'"
        )

    def test_base_pythonunbuffered(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert re.search(r"PYTHONUNBUFFERED\s*=\s*1", base), (
            "Base stage must set PYTHONUNBUFFERED=1"
        )

    def test_base_pythondontwritebytecode(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert re.search(r"PYTHONDONTWRITEBYTECODE\s*=\s*1", base), (
            "Base stage must set PYTHONDONTWRITEBYTECODE=1"
        )

    def test_base_workdir(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        base = stages["base"]
        assert re.search(r"WORKDIR\s+/app", base), "Base stage must set WORKDIR /app"


# ===== Test 11: Dev stage extends base =====
class TestDevStage:
    def test_dev_extends_base(self, dockerfile_content: str):
        assert re.search(r"FROM\s+base\s+AS\s+dev", dockerfile_content, re.IGNORECASE), (
            "Dev stage must extend base"
        )

    def test_dev_installs_dev_extras(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        dev = stages["dev"]
        # Should install dev extras via --extra dev or similar
        assert re.search(r"--extra\s+dev", dev) or "dev" in dev.lower(), (
            "Dev stage must install dev extras"
        )

    def test_dev_copies_backend(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        dev = stages["dev"]
        assert re.search(r"COPY\s+backend/", dev), "Dev stage must copy backend/"

    def test_dev_copies_data(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        dev = stages["dev"]
        assert re.search(r"COPY\s+data/", dev), "Dev stage must copy data/"


# ===== Test 15: Prod stage extends base =====
class TestProdStage:
    def test_prod_extends_base(self, dockerfile_content: str):
        assert re.search(r"FROM\s+base\s+AS\s+prod", dockerfile_content, re.IGNORECASE), (
            "Prod stage must extend base"
        )

    def test_prod_copies_backend(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        prod = stages["prod"]
        assert re.search(r"COPY\s+backend/", prod), "Prod stage must copy backend/"

    def test_prod_copies_data(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        prod = stages["prod"]
        assert re.search(r"COPY\s+data/", prod), "Prod stage must copy data/"

    def test_prod_creates_nonroot_user(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        prod = stages["prod"]
        assert re.search(r"useradd.*appuser", prod), "Prod stage must create appuser"
        assert re.search(r"USER\s+appuser", prod), "Prod stage must switch to appuser"

    def test_prod_exposes_8000(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        prod = stages["prod"]
        assert re.search(r"EXPOSE\s+8000", prod), "Prod stage must EXPOSE 8000"

    def test_prod_cmd_uvicorn(self, dockerfile_content: str):
        stages = _split_stages(dockerfile_content)
        prod = stages["prod"]
        assert "uvicorn" in prod, "Prod CMD must run uvicorn"
        assert "backend.app.main:app" in prod, "Prod CMD must reference backend.app.main:app"
