"""Tests for S12.6 — Deploy to EC2.

Static file validation tests for the deploy script and security practices.
No external services needed — same pattern as S1.1, S1.2, S11.1, S11.4.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy.sh"
GITIGNORE = ROOT / ".gitignore"
ENV_EXAMPLE = ROOT / ".env.example"
PROD_COMPOSE = ROOT / "docker-compose.prod.yml"


# ── Helper ───────────────────────────────────────────────────────────────────


def _read_deploy_script() -> str:
    assert DEPLOY_SCRIPT.exists(), f"deploy.sh not found at {DEPLOY_SCRIPT}"
    return DEPLOY_SCRIPT.read_text()


# ── 1. Deploy script existence & permissions ─────────────────────────────────


class TestDeployScriptExists:
    def test_deploy_script_exists(self):
        assert DEPLOY_SCRIPT.exists(), "scripts/deploy.sh must exist"

    def test_deploy_script_is_file(self):
        assert DEPLOY_SCRIPT.is_file(), "scripts/deploy.sh must be a file"

    def test_deploy_script_is_executable(self):
        mode = DEPLOY_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "deploy.sh must be executable by owner"


# ── 2. Deploy script structure ───────────────────────────────────────────────


class TestDeployScriptStructure:
    def test_deploy_script_has_shebang(self):
        content = _read_deploy_script()
        assert content.startswith("#!/bin/bash"), "deploy.sh must start with #!/bin/bash"

    def test_deploy_script_has_set_euo(self):
        content = _read_deploy_script()
        assert "set -euo pipefail" in content, "deploy.sh must use set -euo pipefail"


# ── 3. Deploy script commands ────────────────────────────────────────────────


class TestDeployScriptCommands:
    def test_deploy_script_pulls_code(self):
        content = _read_deploy_script()
        assert "git pull" in content, "deploy.sh must pull latest code"

    def test_deploy_script_docker_compose_up(self):
        content = _read_deploy_script()
        assert "docker compose -f docker-compose.prod.yml up" in content

    def test_deploy_script_runs_migrations(self):
        content = _read_deploy_script()
        assert "alembic upgrade head" in content

    def test_deploy_script_runs_seed(self):
        content = _read_deploy_script()
        assert "seed.py" in content

    def test_deploy_script_health_check(self):
        content = _read_deploy_script()
        assert "curl" in content and "health" in content

    def test_deploy_script_uses_prod_compose(self):
        content = _read_deploy_script()
        assert "docker-compose.prod.yml" in content
        # Should not use plain docker-compose.yml (dev file)
        lines = content.splitlines()
        for line in lines:
            if "docker compose" in line and "docker-compose.prod.yml" not in line:
                # Allow lines that don't reference compose files at all
                if "-f" in line:
                    pytest.fail(
                        "deploy.sh must use docker-compose.prod.yml, not docker-compose.yml"
                    )

    def test_deploy_script_builds_fresh(self):
        content = _read_deploy_script()
        assert "--build" in content, "deploy.sh must include --build flag"

    def test_deploy_script_detached_mode(self):
        content = _read_deploy_script()
        assert "-d" in content, "deploy.sh must include -d flag for detached mode"

    def test_deploy_script_echoes_completion(self):
        content = _read_deploy_script()
        assert (
            "echo" in content.lower() or "printf" in content.lower()
        ), "deploy.sh must print a completion/status message"


# ── 4. Security: no hardcoded secrets ────────────────────────────────────────


class TestDeployScriptSecurity:
    def test_deploy_script_no_hardcoded_secrets(self):
        content = _read_deploy_script()
        secret_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI / Anthropic keys
            r"AC[a-f0-9]{32}",  # Twilio SID
            r"AKIA[A-Z0-9]{16}",  # AWS access key
        ]
        for pattern in secret_patterns:
            assert not re.search(
                pattern, content
            ), f"deploy.sh must not contain hardcoded secrets matching {pattern}"

    def test_deploy_script_no_hardcoded_ips(self):
        content = _read_deploy_script()
        # Should not hardcode specific Elastic IPs (public IPs like 3.x.x.x, 13.x.x.x)
        # Allow localhost/127.0.0.1
        lines = content.splitlines()
        ip_pattern = re.compile(r"\b(?!127\.0\.0\.1)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
        for line in lines:
            if line.strip().startswith("#"):
                continue
            match = ip_pattern.search(line)
            if match:
                pytest.fail(f"deploy.sh must not hardcode IPs: found {match.group()}")

    def test_deploy_script_no_passwords(self):
        content = _read_deploy_script()
        # Should not contain password= or token= with actual values
        assert not re.search(
            r"(?i)(password|token|secret)=['\"]?[a-zA-Z0-9]{8,}", content
        ), "deploy.sh must not contain hardcoded passwords or tokens"


# ── 5. .env.example has all prod vars ────────────────────────────────────────


class TestEnvExample:
    REQUIRED_VARS = [
        "DATABASE_URL",
        "REDIS_URL",
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
    ]

    def test_env_example_has_all_prod_vars(self):
        content = ENV_EXAMPLE.read_text()
        for var in self.REQUIRED_VARS:
            assert f"{var}=" in content, f".env.example must contain {var}"

    def test_env_example_has_12_variables(self):
        content = ENV_EXAMPLE.read_text()
        var_lines = [
            line
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#") and "=" in line
        ]
        assert len(var_lines) >= 12, f"Expected >= 12 variables, found {len(var_lines)}"


# ── 6. .gitignore security ──────────────────────────────────────────────────


class TestGitignoreSecurity:
    def test_gitignore_excludes_env(self):
        content = GITIGNORE.read_text()
        assert ".env" in content, ".gitignore must exclude .env"

    def test_gitignore_excludes_pem(self):
        content = GITIGNORE.read_text()
        assert "*.pem" in content, ".gitignore must exclude *.pem files"

    def test_env_not_in_git(self):
        """Ensure .env is not tracked by git."""
        content = GITIGNORE.read_text()
        lines = [line.strip() for line in content.splitlines()]
        assert ".env" in lines, ".gitignore must have .env as a standalone entry"


# ── 7. Docker Compose Prod dependency ────────────────────────────────────────


class TestDockerComposeProd:
    def test_docker_compose_prod_exists(self):
        assert PROD_COMPOSE.exists(), "docker-compose.prod.yml must exist"

    def test_docker_compose_prod_uses_env_file(self):
        content = PROD_COMPOSE.read_text()
        assert (
            "env_file" in content or ".env" in content
        ), "docker-compose.prod.yml must reference .env"
