"""Tests for S12.1 — EC2 t3.micro Setup.

Static validation of infrastructure artifacts:
- scripts/ec2-setup.sh (EC2 bootstrap script)
- .github/workflows/deploy.yml (CI/CD pipeline)
- .gitignore (security entries)
"""

import os
import stat
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]  # project root


# ── ec2-setup.sh existence and permissions ──────────────────────────────


class TestEc2SetupScriptExists:
    def test_ec2_setup_script_exists(self):
        assert (ROOT / "scripts" / "ec2-setup.sh").is_file()

    def test_ec2_setup_script_executable(self):
        path = ROOT / "scripts" / "ec2-setup.sh"
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR, "ec2-setup.sh must be executable by owner"


# ── ec2-setup.sh content validation ─────────────────────────────────────


class TestEc2SetupScriptContent:
    SCRIPT = (ROOT / "scripts" / "ec2-setup.sh").read_text()

    def test_has_bash_shebang(self):
        assert self.SCRIPT.startswith("#!/")
        assert "bash" in self.SCRIPT.splitlines()[0]

    def test_has_set_euo_pipefail(self):
        assert "set -euo pipefail" in self.SCRIPT

    def test_installs_docker_ce(self):
        assert "docker-ce" in self.SCRIPT

    def test_installs_docker_compose_plugin(self):
        assert "docker-compose-plugin" in self.SCRIPT

    def test_installs_containerd(self):
        assert "containerd.io" in self.SCRIPT

    def test_adds_user_to_docker_group(self):
        assert "usermod" in self.SCRIPT and "docker" in self.SCRIPT

    def test_enables_docker_on_boot(self):
        assert "systemctl enable docker" in self.SCRIPT

    def test_adds_docker_gpg_key(self):
        assert "docker.gpg" in self.SCRIPT

    def test_adds_docker_apt_repo(self):
        assert "download.docker.com" in self.SCRIPT

    def test_runs_apt_update(self):
        assert "apt-get update" in self.SCRIPT

    def test_no_hardcoded_secrets(self):
        for keyword in ["sk-proj-", "sk-ant-api", "ACxxxxxxx"]:
            assert keyword not in self.SCRIPT, f"Script must not contain '{keyword}'"

    def test_no_hardcoded_ips(self):
        """Script should not hardcode any specific IP addresses."""
        import re

        # Match specific IPs like 1.2.3.4 but not 0.0.0.0 or version numbers
        ips = re.findall(r"\b(?!0\.0\.0\.0)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", self.SCRIPT)
        assert len(ips) == 0, f"Script should not hardcode IPs: {ips}"

    def test_creates_app_directory(self):
        assert "/app" in self.SCRIPT

    def test_prints_completion_message(self):
        assert "complete" in self.SCRIPT.lower() or "done" in self.SCRIPT.lower()


# ── GitHub Actions deploy.yml ────────────────────────────────────────────


class TestDeployWorkflow:
    WORKFLOW_PATH = ROOT / ".github" / "workflows" / "deploy.yml"
    CONTENT = WORKFLOW_PATH.read_text()
    # YAML parses `on:` as boolean True key
    PARSED = yaml.safe_load(CONTENT)
    ON_KEY = PARSED.get("on") or PARSED.get(True, {})

    def test_workflow_file_exists(self):
        assert self.WORKFLOW_PATH.is_file()

    def test_triggers_on_push_to_main(self):
        assert "main" in self.ON_KEY["push"]["branches"]

    def test_has_workflow_dispatch(self):
        assert "workflow_dispatch" in self.ON_KEY

    def test_has_test_job(self):
        assert "test" in self.PARSED["jobs"]

    def test_has_deploy_job(self):
        assert "deploy" in self.PARSED["jobs"]

    def test_deploy_needs_test(self):
        assert "test" in self.PARSED["jobs"]["deploy"]["needs"]

    def test_deploy_only_on_main(self):
        condition = self.PARSED["jobs"]["deploy"]["if"]
        assert "main" in condition

    def test_uses_ssh_action(self):
        """Deploy job uses appleboy/ssh-action for SSH deployment."""
        deploy_steps = self.PARSED["jobs"]["deploy"]["steps"]
        uses_list = [s.get("uses", "") for s in deploy_steps]
        assert any("ssh-action" in u for u in uses_list)

    def test_references_ec2_host_secret(self):
        assert "EC2_HOST" in self.CONTENT

    def test_references_ec2_ssh_key_secret(self):
        assert "EC2_SSH_KEY" in self.CONTENT

    def test_references_all_env_secrets(self):
        """All required env vars from .env.example should be in workflow secrets.

        AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are excluded — EC2 uses
        IAM role for S3 access instead of hardcoded credentials.
        """
        required = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_WHATSAPP_FROM",
            "BHASHINI_API_KEY",
            "BHASHINI_USER_ID",
            "S3_BUCKET",
            "DATABASE_URL",
            "REDIS_URL",
        ]
        for var in required:
            assert var in self.CONTENT, f"Workflow must reference secret: {var}"

    def test_runs_docker_compose_up(self):
        assert "docker compose" in self.CONTENT and "up" in self.CONTENT

    def test_runs_alembic_migration(self):
        assert "alembic" in self.CONTENT and "upgrade head" in self.CONTENT

    def test_runs_seed_script(self):
        assert "scripts.seed" in self.CONTENT or "seed.py" in self.CONTENT

    def test_runs_health_check(self):
        assert "health" in self.CONTENT

    def test_uses_prod_compose_file(self):
        assert "docker-compose.prod.yml" in self.CONTENT

    def test_no_hardcoded_secrets_in_workflow(self):
        """Workflow should only reference secrets via ${{ secrets.* }}."""
        for keyword in ["sk-", "sk-ant-", "ACxxxxxxx"]:
            assert keyword not in self.CONTENT

    def test_test_job_runs_pytest(self):
        test_steps = self.PARSED["jobs"]["test"]["steps"]
        step_runs = [s.get("run", "") for s in test_steps]
        assert any("pytest" in r for r in step_runs)

    def test_test_job_runs_lint(self):
        test_steps = self.PARSED["jobs"]["test"]["steps"]
        step_runs = [s.get("run", "") for s in test_steps]
        assert any("ruff" in r for r in step_runs)


# ── .gitignore security ──────────────────────────────────────────────────


class TestGitignoreSecurity:
    GITIGNORE = (ROOT / ".gitignore").read_text()

    def test_env_in_gitignore(self):
        assert ".env" in self.GITIGNORE

    def test_pem_in_gitignore(self):
        assert "*.pem" in self.GITIGNORE
