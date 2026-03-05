"""Tests for S11.3 — Docker Compose Prod.

All tests are static YAML file validation (pure file reads + assertions).
No mocking needed.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD_COMPOSE = ROOT / "docker-compose.prod.yml"
DEV_COMPOSE = ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def prod_data() -> dict:
    """Load and parse the prod compose file once."""
    assert PROD_COMPOSE.exists(), f"{PROD_COMPOSE} not found"
    return yaml.safe_load(PROD_COMPOSE.read_text())


@pytest.fixture(scope="module")
def dev_data() -> dict:
    """Load and parse the dev compose file once."""
    assert DEV_COMPOSE.exists(), f"{DEV_COMPOSE} not found"
    return yaml.safe_load(DEV_COMPOSE.read_text())


# ── File existence & validity ────────────────────────────────────────────────


class TestFileBasics:
    def test_prod_compose_file_exists(self):
        assert PROD_COMPOSE.exists(), "docker-compose.prod.yml must exist at project root"

    def test_prod_compose_valid_yaml(self):
        data = yaml.safe_load(PROD_COMPOSE.read_text())
        assert isinstance(data, dict), "Must parse as a YAML mapping"

    def test_prod_compose_has_services_key(self, prod_data):
        assert "services" in prod_data, "Top-level 'services' key required"


# ── Service definitions ──────────────────────────────────────────────────────


class TestServiceDefinitions:
    def test_prod_compose_app_service_exists(self, prod_data):
        assert "app" in prod_data["services"], "'app' service must be defined"

    def test_prod_compose_no_postgres_service(self, prod_data):
        assert "postgres" not in prod_data["services"], "Prod must NOT define a postgres service"

    def test_prod_compose_no_redis_service(self, prod_data):
        assert "redis" not in prod_data["services"], "Prod must NOT define a redis service"

    def test_prod_compose_only_app_service(self, prod_data):
        services = list(prod_data["services"].keys())
        assert services == ["app"], f"Only 'app' service expected, got {services}"


# ── Build configuration ──────────────────────────────────────────────────────


class TestBuildConfig:
    def test_prod_compose_build_context(self, prod_data):
        build = prod_data["services"]["app"]["build"]
        assert build["context"] == ".", "Build context must be repo root '.'"

    def test_prod_compose_build_dockerfile(self, prod_data):
        build = prod_data["services"]["app"]["build"]
        assert build["dockerfile"] == "backend/Dockerfile"

    def test_prod_compose_build_target_prod(self, prod_data):
        build = prod_data["services"]["app"]["build"]
        assert build["target"] == "prod", "Build target must be 'prod'"


# ── Port exposure ────────────────────────────────────────────────────────────


class TestPorts:
    def test_prod_compose_port_8000(self, prod_data):
        ports = prod_data["services"]["app"]["ports"]
        port_strs = [str(p) for p in ports]
        assert "8000:8000" in port_strs, "Port 8000:8000 must be exposed"


# ── Environment ──────────────────────────────────────────────────────────────


class TestEnvironment:
    def test_prod_compose_env_file(self, prod_data):
        app = prod_data["services"]["app"]
        env_file = app.get("env_file")
        # Accept string or list
        if isinstance(env_file, list):
            assert ".env" in env_file
        else:
            assert env_file == ".env", "env_file must be '.env'"

    def test_prod_compose_no_hardcoded_database_url(self, prod_data):
        app = prod_data["services"]["app"]
        env = app.get("environment", {})
        if env:
            if isinstance(env, dict):
                assert "DATABASE_URL" not in env, (
                    "DATABASE_URL must NOT be hardcoded in environment"
                )
            elif isinstance(env, list):
                for item in env:
                    assert not str(item).startswith("DATABASE_URL="), (
                        "DATABASE_URL must NOT be hardcoded"
                    )

    def test_prod_compose_no_hardcoded_redis_url(self, prod_data):
        app = prod_data["services"]["app"]
        env = app.get("environment", {})
        if env:
            if isinstance(env, dict):
                assert "REDIS_URL" not in env, "REDIS_URL must NOT be hardcoded in environment"
            elif isinstance(env, list):
                for item in env:
                    assert not str(item).startswith("REDIS_URL="), "REDIS_URL must NOT be hardcoded"


# ── Restart policy ───────────────────────────────────────────────────────────


class TestRestartPolicy:
    def test_prod_compose_restart_policy(self, prod_data):
        app = prod_data["services"]["app"]
        assert app.get("restart") == "unless-stopped", "Restart policy must be 'unless-stopped'"


# ── No dev artifacts ─────────────────────────────────────────────────────────


class TestNoProdDevArtifacts:
    def test_prod_compose_no_source_volumes(self, prod_data):
        app = prod_data["services"]["app"]
        volumes = app.get("volumes", [])
        for v in volumes:
            v_str = str(v)
            assert "./backend" not in v_str, "Must NOT mount ./backend as volume"
            assert "./data" not in v_str, "Must NOT mount ./data as volume"

    def test_prod_compose_no_reload_flag(self, prod_data):
        app = prod_data["services"]["app"]
        command = app.get("command", "")
        assert "--reload" not in str(command), "Prod must NOT use --reload"

    def test_prod_compose_no_depends_on(self, prod_data):
        app = prod_data["services"]["app"]
        assert "depends_on" not in app, "No depends_on — no local services to depend on in prod"

    def test_prod_compose_no_volumes_section(self, prod_data):
        assert "volumes" not in prod_data, (
            "No top-level 'volumes' key — no named volumes needed in prod"
        )


# ── Comparison with dev ──────────────────────────────────────────────────────


class TestDiffFromDev:
    def test_prod_compose_differs_from_dev(self, prod_data, dev_data):
        """Prod must differ from dev in at least: target, services count, volumes."""
        prod_target = prod_data["services"]["app"]["build"]["target"]
        dev_target = dev_data["services"]["app"]["build"]["target"]
        assert prod_target != dev_target, "Prod and dev must use different build targets"

        prod_services = set(prod_data["services"].keys())
        dev_services = set(dev_data["services"].keys())
        assert prod_services != dev_services, "Prod and dev must have different service sets"
