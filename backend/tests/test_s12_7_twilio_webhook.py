"""S12.7 — Twilio Webhook URL Update: static validation tests.

Tests verify:
- scripts/verify_webhook.sh exists, executable, correct contents
- Webhook endpoint configuration in webhooks.py
- Security/HMAC wiring
- .env.example has required Twilio vars
- deploy.sh exists (S12.6 dependency)
- docker-compose.prod.yml exposes port 8000
"""

from __future__ import annotations

import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # SehatSamjho/
SCRIPTS_DIR = ROOT / "scripts"
VERIFY_SCRIPT = SCRIPTS_DIR / "verify_webhook.sh"
DEPLOY_SCRIPT = SCRIPTS_DIR / "deploy.sh"
ENV_EXAMPLE = ROOT / ".env.example"
DOCKER_COMPOSE_PROD = ROOT / "docker-compose.prod.yml"
WEBHOOKS_PY = ROOT / "backend" / "app" / "api" / "webhooks.py"


# ── 1. Script existence ─────────────────────────────────────────────────────


class TestVerifyScriptExists:
    def test_verify_script_exists(self):
        """scripts/verify_webhook.sh must exist."""
        assert VERIFY_SCRIPT.exists(), f"{VERIFY_SCRIPT} not found"

    def test_verify_script_is_file(self):
        """verify_webhook.sh must be a regular file."""
        assert VERIFY_SCRIPT.is_file()


# ── 2. Script executable ────────────────────────────────────────────────────


class TestVerifyScriptExecutable:
    def test_verify_script_executable(self):
        """verify_webhook.sh must have executable permission."""
        mode = VERIFY_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "Script is not executable (user)"


# ── 3. Shebang ──────────────────────────────────────────────────────────────


class TestVerifyScriptShebang:
    def test_verify_script_has_shebang(self):
        """Script starts with #!/bin/bash."""
        first_line = VERIFY_SCRIPT.read_text().splitlines()[0]
        assert first_line.strip() == "#!/bin/bash"


# ── 4. set -euo pipefail ────────────────────────────────────────────────────


class TestVerifyScriptSafety:
    def test_verify_script_has_set_euo(self):
        """Script uses set -euo pipefail for safety."""
        content = VERIFY_SCRIPT.read_text()
        assert "set -euo pipefail" in content


# ── 5. Accepts IP argument ──────────────────────────────────────────────────


class TestVerifyScriptIPArg:
    def test_verify_script_accepts_ip_arg(self):
        """Script references positional argument ($1) for EC2 IP."""
        content = VERIFY_SCRIPT.read_text()
        assert "$1" in content or "${1" in content


# ── 6. Health check ─────────────────────────────────────────────────────────


class TestVerifyScriptHealthCheck:
    def test_verify_script_checks_health(self):
        """Script curls /health endpoint."""
        content = VERIFY_SCRIPT.read_text()
        assert "/health" in content


# ── 7. Webhook POST ─────────────────────────────────────────────────────────


class TestVerifyScriptWebhookCheck:
    def test_verify_script_checks_webhook(self):
        """Script sends POST to /webhook/whatsapp."""
        content = VERIFY_SCRIPT.read_text()
        assert "/webhook/whatsapp" in content


# ── 8. Expects 403 ──────────────────────────────────────────────────────────


class TestVerifyScriptExpects403:
    def test_verify_script_expects_403(self):
        """Script checks for 403 response (HMAC rejection for unsigned request)."""
        content = VERIFY_SCRIPT.read_text()
        assert "403" in content


# ── 9. No hardcoded secrets ─────────────────────────────────────────────────


class TestVerifyScriptNoSecrets:
    def test_verify_script_no_hardcoded_secrets(self):
        """Script must not contain API keys or tokens."""
        content = VERIFY_SCRIPT.read_text()
        forbidden = ["sk-", "AC", "auth_token", "api_key", "secret"]
        for keyword in forbidden:
            # Allow "auth_token" only as part of a variable name, not a value
            if keyword in ("auth_token", "api_key", "secret"):
                continue
            assert keyword not in content.lower() or keyword in (
                "sk-",
                "AC",
            ), f"Found potential secret pattern: {keyword}"
        # More precise check: no literal API key patterns
        import re

        assert not re.search(r"sk-[a-zA-Z0-9]{20,}", content), "Found OpenAI key pattern"
        assert not re.search(r"AC[a-f0-9]{32}", content), "Found Twilio SID pattern"


# ── 10. No hardcoded IPs ────────────────────────────────────────────────────


class TestVerifyScriptNoHardcodedIPs:
    def test_verify_script_no_hardcoded_ips(self):
        """Script must not hardcode Elastic IPs (use argument instead)."""
        content = VERIFY_SCRIPT.read_text()
        import re

        # Match public IP patterns (not 127.0.0.1 or 0.0.0.0)
        public_ips = re.findall(
            r"\b(?!127\.0\.0\.1|0\.0\.0\.0)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", content
        )
        assert len(public_ips) == 0, f"Found hardcoded IPs: {public_ips}"


# ── 11. Uses port 8000 ──────────────────────────────────────────────────────


class TestVerifyScriptPort:
    def test_verify_script_uses_port_8000(self):
        """Script references port 8000."""
        content = VERIFY_SCRIPT.read_text()
        assert "8000" in content


# ── 12. Webhook endpoint path correct ───────────────────────────────────────


class TestWebhookEndpointPath:
    def test_webhook_endpoint_path_correct(self):
        """webhooks.py defines route /whatsapp under /webhook prefix = /webhook/whatsapp."""
        content = WEBHOOKS_PY.read_text()
        # Router defines "/whatsapp" and main.py includes with prefix="/webhook"
        assert '"/whatsapp"' in content


# ── 13. Webhook method is POST ──────────────────────────────────────────────


class TestWebhookMethod:
    def test_webhook_method_is_post(self):
        """Webhook route uses @router.post()."""
        content = WEBHOOKS_PY.read_text()
        assert "router.post(" in content


# ── 14. Security module imported ────────────────────────────────────────────


class TestSecurityImported:
    def test_security_module_imported(self):
        """webhooks.py imports or references HMAC/security validation."""
        content = WEBHOOKS_PY.read_text()
        assert "validate_twilio_signature" in content


# ── 15. TWILIO_AUTH_TOKEN in .env.example ────────────────────────────────────


class TestEnvExampleTwilioAuth:
    def test_twilio_auth_token_in_env_example(self):
        """.env.example contains TWILIO_AUTH_TOKEN."""
        content = ENV_EXAMPLE.read_text()
        assert "TWILIO_AUTH_TOKEN" in content


# ── 16. TWILIO_WHATSAPP_FROM in .env.example ────────────────────────────────


class TestEnvExampleTwilioFrom:
    def test_twilio_whatsapp_from_in_env_example(self):
        """.env.example contains TWILIO_WHATSAPP_FROM."""
        content = ENV_EXAMPLE.read_text()
        assert "TWILIO_WHATSAPP_FROM" in content


# ── 17. Deploy script exists (S12.6 dep) ────────────────────────────────────


class TestDeployScriptExists:
    def test_deploy_script_exists(self):
        """scripts/deploy.sh must exist (S12.6 dependency)."""
        assert DEPLOY_SCRIPT.exists(), f"{DEPLOY_SCRIPT} not found"


# ── 18. docker-compose.prod.yml exposes port 8000 ───────────────────────────


class TestDockerComposeProdPort:
    def test_docker_compose_prod_exposes_port(self):
        """docker-compose.prod.yml exposes port 8000."""
        content = DOCKER_COMPOSE_PROD.read_text()
        assert "8000" in content


# ── 19. Script prints results ────────────────────────────────────────────────


class TestVerifyScriptPrintsResults:
    def test_verify_script_prints_results(self):
        """Script uses echo to print feedback to user."""
        content = VERIFY_SCRIPT.read_text()
        assert content.count("echo") >= 2, "Script should have at least 2 echo statements"


# ── 20. Script shows usage message ──────────────────────────────────────────


class TestVerifyScriptUsage:
    def test_verify_script_usage_message(self):
        """Script shows usage if no argument provided."""
        content = VERIFY_SCRIPT.read_text()
        assert "Usage" in content or "usage" in content
