"""Tests for S11.4 — Docker Ignore Rules.

Static file validation tests for .dockerignore at repository root.
No mocking needed — pure file content inspection.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"


@pytest.fixture
def dockerignore_content() -> str:
    """Read .dockerignore content."""
    assert DOCKERIGNORE_PATH.exists(), f".dockerignore not found at {DOCKERIGNORE_PATH}"
    return DOCKERIGNORE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def dockerignore_lines(dockerignore_content: str) -> list[str]:
    """Return all non-empty, non-comment lines (stripped)."""
    return [
        line.strip()
        for line in dockerignore_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------- Test 1: File exists ----------
class TestDockerignoreExists:
    def test_dockerignore_exists(self):
        """T1: .dockerignore file exists at repository root."""
        assert DOCKERIGNORE_PATH.exists(), ".dockerignore must exist at repo root"

    def test_dockerignore_not_empty(self, dockerignore_content: str):
        """T2: .dockerignore is not empty."""
        assert len(dockerignore_content.strip()) > 0, ".dockerignore must not be empty"


# ----------Test 3-4: Python environment exclusions (FR-1) ----------
class TestPythonEnvironment:
    def test_excludes_venv(self, dockerignore_lines: list[str]):
        """T3: .venv directory is excluded."""
        assert any(".venv" in line for line in dockerignore_lines), ".venv must be in .dockerignore"

    def test_excludes_pycache(self, dockerignore_lines: list[str]):
        """T5: __pycache__ directories are excluded."""
        assert any("__pycache__" in line for line in dockerignore_lines), (
            "__pycache__ must be in .dockerignore"
        )

    def test_excludes_pyc(self, dockerignore_lines: list[str]):
        """T6: *.pyc files are excluded."""
        assert any("*.pyc" in line for line in dockerignore_lines), "*.pyc must be in .dockerignore"


# ---------- Test 5-6: Environment secrets (FR-2) ----------
class TestSecrets:
    def test_excludes_env_files(self, dockerignore_lines: list[str]):
        """T4: .env files are excluded."""
        assert any(
            ".env" in line and "example" not in line.lower() for line in dockerignore_lines
        ), ".env must be in .dockerignore"

    def test_excludes_env_wildcard(self, dockerignore_lines: list[str]):
        """T4b: .env.* pattern or .env is covered."""
        env_patterns = [line for line in dockerignore_lines if ".env" in line]
        assert len(env_patterns) >= 1, ".env pattern must be in .dockerignore"


# ---------- Test 7: VCS metadata (FR-4) ----------
class TestVCS:
    def test_excludes_git(self, dockerignore_lines: list[str]):
        """T7: .git directory is excluded."""
        assert any(line == ".git" or line == ".git/" for line in dockerignore_lines), (
            ".git must be in .dockerignore"
        )


# ---------- Test 8-10: Documentation directories (FR-5) ----------
class TestDocumentation:
    def test_excludes_notebooks(self, dockerignore_lines: list[str]):
        """T8: notebooks/ directory is excluded."""
        assert any("notebooks" in line for line in dockerignore_lines), (
            "notebooks/ must be in .dockerignore"
        )

    def test_excludes_docs(self, dockerignore_lines: list[str]):
        """T9: docs/ directory is excluded."""
        assert any(
            "docs" in line and "docker" not in line.lower() for line in dockerignore_lines
        ), "docs/ must be in .dockerignore"

    def test_excludes_specs(self, dockerignore_lines: list[str]):
        """T10: specs/ directory is excluded."""
        assert any("specs" in line for line in dockerignore_lines), (
            "specs/ must be in .dockerignore"
        )


# ---------- Test 11-12: Data files (FR-6) ----------
class TestDataFiles:
    def test_excludes_drug_csv_data(self, dockerignore_lines: list[str]):
        """T11: Drug CSV data files are excluded."""
        assert any(
            "data/drugs" in line or ("data" in line and "csv" in line.lower())
            for line in dockerignore_lines
        ), "Drug CSV data must be excluded in .dockerignore"

    def test_does_not_exclude_glossary(self, dockerignore_content: str):
        """T12: data/glossary/ is NOT excluded (or explicitly included via !)."""
        lines = [
            line.strip()
            for line in dockerignore_content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        # Either glossary is explicitly included with ! override, or not mentioned at all
        has_negation = any("!data/glossary" in line for line in lines)
        has_exclusion = any(line == "data/glossary" or line == "data/glossary/" for line in lines)
        assert has_negation or not has_exclusion, (
            "data/glossary/ must NOT be excluded (or must have ! override)"
        )


# ---------- Test 13-15: Test/dev artifacts (FR-7) ----------
class TestDevArtifacts:
    def test_excludes_tests(self, dockerignore_lines: list[str]):
        """T13: backend/tests/ directory is excluded."""
        assert any("tests" in line for line in dockerignore_lines), (
            "Test directory must be in .dockerignore"
        )

    def test_excludes_pytest_cache(self, dockerignore_lines: list[str]):
        """T14: .pytest_cache is excluded."""
        assert any(".pytest_cache" in line for line in dockerignore_lines), (
            ".pytest_cache must be in .dockerignore"
        )

    def test_excludes_ruff_cache(self, dockerignore_lines: list[str]):
        """T15: .ruff_cache is excluded."""
        assert any(".ruff_cache" in line for line in dockerignore_lines), (
            ".ruff_cache must be in .dockerignore"
        )


# ---------- Test 16-17: Docker config files (FR-8) ----------
class TestDockerConfig:
    def test_excludes_dockerfile(self, dockerignore_lines: list[str]):
        """T16: Dockerfile is excluded."""
        assert any(line == "Dockerfile" or line == "Dockerfile*" for line in dockerignore_lines), (
            "Dockerfile must be in .dockerignore"
        )

    def test_excludes_docker_compose(self, dockerignore_lines: list[str]):
        """T17: docker-compose*.yml is excluded."""
        assert any("docker-compose" in line for line in dockerignore_lines), (
            "docker-compose*.yml must be in .dockerignore"
        )


# ---------- Test 18-20: Syntax and quality ----------
class TestSyntaxAndQuality:
    def test_valid_syntax(self, dockerignore_content: str):
        """T18: Every non-empty, non-comment line is a valid pattern (no trailing spaces)."""
        for i, line in enumerate(dockerignore_content.splitlines(), start=1):
            if line.strip() and not line.strip().startswith("#"):
                assert line == line.rstrip(), f"Line {i} has trailing whitespace: {line!r}"

    def test_has_comments(self, dockerignore_content: str):
        """T19: File includes descriptive comment sections."""
        comment_lines = [
            line for line in dockerignore_content.splitlines() if line.strip().startswith("#")
        ]
        assert len(comment_lines) >= 3, "File should have at least 3 comment lines for organization"

    def test_no_duplicate_patterns(self, dockerignore_lines: list[str]):
        """T20: No exact duplicate lines."""
        seen = set()
        duplicates = []
        for line in dockerignore_lines:
            if line in seen:
                duplicates.append(line)
            seen.add(line)
        assert not duplicates, f"Duplicate patterns found: {duplicates}"
