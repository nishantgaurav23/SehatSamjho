"""S2.5 — Alembic Migrations Setup Tests.

All tests are static file/config validation — no DB connection needed.
20 tests covering all Functional Requirements.
"""

import configparser
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # SehatSamjho/
BACKEND_DIR = PROJECT_ROOT / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"
ENV_PY = ALEMBIC_DIR / "env.py"
SCRIPT_MAKO = ALEMBIC_DIR / "script.py.mako"
VERSIONS_DIR = ALEMBIC_DIR / "versions"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _read_ini() -> configparser.ConfigParser:
    """Parse alembic.ini and return the ConfigParser."""
    cp = configparser.ConfigParser()
    cp.read(str(ALEMBIC_INI))
    return cp


def _find_migration_files() -> list[Path]:
    """Return all .py files in versions/ (excluding __pycache__)."""
    if not VERSIONS_DIR.exists():
        return []
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def _read_first_migration() -> str:
    """Read the source of the first migration file."""
    files = _find_migration_files()
    assert len(files) >= 1, "No migration files found in versions/"
    return files[0].read_text()


# ── FR-1: alembic.ini ───────────────────────────────────────────────────────


class TestAlembicIni:
    """Tests for alembic.ini configuration (FR-1)."""

    def test_alembic_ini_exists(self):
        """alembic.ini exists at backend/alembic.ini."""
        assert ALEMBIC_INI.exists(), f"Expected {ALEMBIC_INI} to exist"

    def test_alembic_ini_script_location(self):
        """script_location = alembic."""
        cp = _read_ini()
        assert cp.get("alembic", "script_location") == "alembic"

    def test_alembic_ini_prepend_sys_path(self):
        """prepend_sys_path includes '..' so backend.app.* imports resolve."""
        cp = _read_ini()
        val = cp.get("alembic", "prepend_sys_path")
        assert ".." in val

    def test_alembic_ini_no_hardcoded_url(self):
        """sqlalchemy.url is empty or placeholder — never a real connection string."""
        cp = _read_ini()
        url = cp.get("alembic", "sqlalchemy.url", fallback="")
        # Must not look like a real postgres/sqlite URL
        assert "postgresql" not in url.lower()
        assert "sqlite" not in url.lower()
        assert "@" not in url  # no user:pass@host pattern


# ── FR-2: env.py ────────────────────────────────────────────────────────────


class TestEnvPy:
    """Tests for alembic/env.py (FR-2)."""

    def test_env_py_exists(self):
        """env.py exists at backend/alembic/env.py."""
        assert ENV_PY.exists(), f"Expected {ENV_PY} to exist"

    def test_env_py_imports_base(self):
        """env.py imports Base from backend.app.db.database."""
        src = ENV_PY.read_text()
        assert "backend.app.db.database" in src
        assert "Base" in src

    def test_env_py_imports_models(self):
        """env.py imports backend.app.db.models so autogenerate sees all tables."""
        src = ENV_PY.read_text()
        assert "backend.app.db.models" in src

    def test_env_py_uses_async_engine(self):
        """env.py uses create_async_engine or async_engine_from_config."""
        src = ENV_PY.read_text()
        assert ("create_async_engine" in src) or ("async_engine_from_config" in src)

    def test_env_py_uses_settings_database_url(self):
        """env.py reads settings.DATABASE_URL at runtime."""
        src = ENV_PY.read_text()
        assert "settings.DATABASE_URL" in src or "settings.database_url" in src


# ── FR-3: script.py.mako ────────────────────────────────────────────────────


class TestScriptMako:
    """Tests for alembic/script.py.mako (FR-3)."""

    def test_script_mako_exists(self):
        """script.py.mako exists at backend/alembic/script.py.mako."""
        assert SCRIPT_MAKO.exists(), f"Expected {SCRIPT_MAKO} to exist"

    def test_script_mako_has_revision(self):
        """Template contains revision and down_revision variables."""
        src = SCRIPT_MAKO.read_text()
        assert "revision" in src
        assert "down_revision" in src


# ── FR-4: Initial Migration ─────────────────────────────────────────────────


class TestInitialMigration:
    """Tests for the initial migration file (FR-4)."""

    def test_versions_dir_exists(self):
        """backend/alembic/versions/ directory exists."""
        assert VERSIONS_DIR.exists() and VERSIONS_DIR.is_dir()

    def test_initial_migration_exists(self):
        """At least one .py migration file exists in versions/."""
        files = _find_migration_files()
        assert len(files) >= 1, "No migration files found"

    def test_initial_migration_has_upgrade(self):
        """Migration defines an upgrade() function."""
        src = _read_first_migration()
        assert "def upgrade()" in src

    def test_initial_migration_has_downgrade(self):
        """Migration defines a downgrade() function."""
        src = _read_first_migration()
        assert "def downgrade()" in src

    def test_initial_migration_creates_interaction_log(self):
        """upgrade() contains create_table with 'interaction_log'."""
        src = _read_first_migration()
        assert "create_table" in src
        assert "interaction_log" in src

    def test_initial_migration_downgrade_drops_table(self):
        """downgrade() contains drop_table with 'interaction_log'."""
        src = _read_first_migration()
        # Find downgrade function body
        idx = src.index("def downgrade()")
        downgrade_body = src[idx:]
        assert "drop_table" in downgrade_body
        assert "interaction_log" in downgrade_body

    def test_interaction_log_columns_in_migration(self):
        """All 9 column names appear in the migration file."""
        src = _read_first_migration()
        expected_columns = [
            "id",
            "created_at",
            "phone_hash",
            "language_code",
            "doc_type",
            "confidence_avg",
            "latency_ms",
            "status",
            "error_code",
        ]
        for col in expected_columns:
            assert col in src, f"Column '{col}' not found in migration"


# ── FR-5: Dependency in pyproject.toml ───────────────────────────────────────


class TestAlembicDependency:
    """Tests for alembic dependency (FR-5)."""

    def test_alembic_dependency_in_pyproject(self):
        """alembic>=1.12 is listed in pyproject.toml dependencies."""
        content = PYPROJECT.read_text()
        assert "alembic>=1.12" in content


# ── Config loadable ──────────────────────────────────────────────────────────


class TestAlembicConfig:
    """Test that Alembic config is parseable."""

    def test_alembic_config_loadable(self):
        """alembic.config.Config can load backend/alembic.ini without errors."""
        from alembic.config import Config

        cfg = Config(str(ALEMBIC_INI))
        assert cfg.get_main_option("script_location") == "alembic"
