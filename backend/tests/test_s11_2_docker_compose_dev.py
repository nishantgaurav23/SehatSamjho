"""
Tests for S11.2 — Docker Compose Dev (Local development stack).

All tests are static file validation: parse docker-compose.yml YAML and assert structure.
No Docker daemon or mocking needed.
"""

from pathlib import Path

import yaml
import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"
MAKEFILE = PROJECT_ROOT / "Makefile"


@pytest.fixture(scope="module")
def compose() -> dict:
    """Parse docker-compose.yml once for all tests."""
    assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"
    return yaml.safe_load(COMPOSE_FILE.read_text())


# ── FR-1: Compose file version and structure ─────────────────────────────────


class TestComposeFile:
    """FR-1: Valid YAML, 3 services."""

    def test_compose_file_exists(self):
        assert COMPOSE_FILE.exists()

    def test_compose_valid_yaml(self, compose):
        assert isinstance(compose, dict)

    def test_compose_has_services(self, compose):
        assert "services" in compose
        assert set(compose["services"].keys()) == {"postgres", "redis", "app"}


# ── FR-2: PostgreSQL service ─────────────────────────────────────────────────


class TestPostgresService:
    """FR-2: postgres:15 with env, ports, volume, healthcheck."""

    def test_postgres_service_image(self, compose):
        pg = compose["services"]["postgres"]
        assert pg["image"] == "postgres:15"

    def test_postgres_service_environment(self, compose):
        pg = compose["services"]["postgres"]
        env = pg["environment"]
        # env can be list ["K=V"] or dict {"K": "V"}
        if isinstance(env, list):
            env_dict = dict(e.split("=", 1) for e in env)
        else:
            env_dict = env
        assert env_dict["POSTGRES_USER"] == "postgres"
        assert env_dict["POSTGRES_PASSWORD"] == "postgres"
        assert env_dict["POSTGRES_DB"] == "sehatsamjho"

    def test_postgres_service_ports(self, compose):
        pg = compose["services"]["postgres"]
        ports = [str(p) for p in pg["ports"]]
        assert any("5432" in p for p in ports)

    def test_postgres_service_volume(self, compose):
        pg = compose["services"]["postgres"]
        volumes = pg["volumes"]
        vol_strs = [
            str(v) if isinstance(v, str) else f"{v['source']}:{v['target']}" for v in volumes
        ]
        assert any("postgres_data" in v and "/var/lib/postgresql/data" in v for v in vol_strs)

    def test_postgres_service_healthcheck(self, compose):
        pg = compose["services"]["postgres"]
        hc = pg["healthcheck"]
        # test can be string or list
        test_cmd = hc["test"]
        if isinstance(test_cmd, list):
            test_str = " ".join(test_cmd)
        else:
            test_str = test_cmd
        assert "pg_isready" in test_str


# ── FR-3: Redis service ──────────────────────────────────────────────────────


class TestRedisService:
    """FR-3: redis:7 with healthcheck."""

    def test_redis_service_image(self, compose):
        r = compose["services"]["redis"]
        assert r["image"] == "redis:7"

    def test_redis_service_ports(self, compose):
        r = compose["services"]["redis"]
        ports = [str(p) for p in r["ports"]]
        assert any("6379" in p for p in ports)

    def test_redis_service_healthcheck(self, compose):
        r = compose["services"]["redis"]
        hc = r["healthcheck"]
        test_cmd = hc["test"]
        if isinstance(test_cmd, list):
            test_str = " ".join(test_cmd)
        else:
            test_str = test_cmd
        assert "redis-cli" in test_str and "ping" in test_str


# ── FR-4: Application service ────────────────────────────────────────────────


class TestAppService:
    """FR-4: App service built from Dockerfile dev stage."""

    def test_app_service_build_context(self, compose):
        app = compose["services"]["app"]
        build = app["build"]
        if isinstance(build, str):
            assert build == "."
        else:
            assert build["context"] == "."

    def test_app_service_build_target(self, compose):
        app = compose["services"]["app"]
        build = app["build"]
        assert isinstance(build, dict), "build must be a mapping with target"
        assert build["target"] == "dev"

    def test_app_service_ports(self, compose):
        app = compose["services"]["app"]
        ports = [str(p) for p in app["ports"]]
        assert any("8000" in p for p in ports)

    def test_app_service_env_file(self, compose):
        app = compose["services"]["app"]
        env_file = app["env_file"]
        if isinstance(env_file, list):
            assert ".env" in env_file
        else:
            assert env_file == ".env"

    def test_app_service_database_url_override(self, compose):
        app = compose["services"]["app"]
        env = app["environment"]
        if isinstance(env, list):
            env_dict = dict(e.split("=", 1) for e in env)
        else:
            env_dict = env
        db_url = env_dict["DATABASE_URL"]
        assert "postgres" in db_url, "DATABASE_URL should use docker service hostname 'postgres'"
        assert "localhost" not in db_url, "DATABASE_URL must not use localhost"
        assert "asyncpg" in db_url

    def test_app_service_redis_url_override(self, compose):
        app = compose["services"]["app"]
        env = app["environment"]
        if isinstance(env, list):
            env_dict = dict(e.split("=", 1) for e in env)
        else:
            env_dict = env
        redis_url = env_dict["REDIS_URL"]
        assert "redis://redis" in redis_url, "REDIS_URL should use docker service hostname 'redis'"
        assert "localhost" not in redis_url

    def test_app_service_depends_on_postgres(self, compose):
        app = compose["services"]["app"]
        deps = app["depends_on"]
        assert "postgres" in deps
        pg_dep = deps["postgres"]
        assert pg_dep["condition"] == "service_healthy"

    def test_app_service_depends_on_redis(self, compose):
        app = compose["services"]["app"]
        deps = app["depends_on"]
        assert "redis" in deps
        redis_dep = deps["redis"]
        assert redis_dep["condition"] == "service_healthy"

    def test_app_service_command(self, compose):
        app = compose["services"]["app"]
        cmd = app["command"]
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        assert "uvicorn" in cmd_str
        assert "--reload" in cmd_str

    def test_app_service_bind_mount_backend(self, compose):
        app = compose["services"]["app"]
        volumes = app["volumes"]
        vol_strs = [
            str(v) if isinstance(v, str) else f"{v['source']}:{v['target']}" for v in volumes
        ]
        assert any("./backend" in v and "/app/backend" in v for v in vol_strs), (
            f"Expected bind mount ./backend:/app/backend, got {vol_strs}"
        )

    def test_app_service_bind_mount_data(self, compose):
        app = compose["services"]["app"]
        volumes = app["volumes"]
        vol_strs = [
            str(v) if isinstance(v, str) else f"{v['source']}:{v['target']}" for v in volumes
        ]
        assert any("./data" in v and "/app/data" in v for v in vol_strs), (
            f"Expected bind mount ./data:/app/data, got {vol_strs}"
        )


# ── FR-5: Named volumes ──────────────────────────────────────────────────────


class TestNamedVolumes:
    """FR-5: Top-level volumes declares postgres_data."""

    def test_named_volume_postgres_data(self, compose):
        assert "volumes" in compose, "Top-level 'volumes' key must exist"
        assert "postgres_data" in compose["volumes"]


# ── FR-6: Makefile compatibility ──────────────────────────────────────────────


class TestMakefileCompatibility:
    """FR-6: Existing Makefile Docker targets work with compose file."""

    def test_makefile_dev_target_compatible(self):
        content = MAKEFILE.read_text()
        assert "docker compose up --build" in content
