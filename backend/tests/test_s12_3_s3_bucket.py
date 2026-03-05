"""Tests for S12.3 — S3 Bucket Setup.

Static validation of infrastructure artifacts:
- scripts/setup-s3.sh (S3 bucket creation + configuration script)
- scripts/validate-s3.sh (S3 bucket validation script)
"""

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # project root


# ── setup-s3.sh existence and permissions ──────────────────────────────


class TestSetupS3ScriptExists:
    def test_setup_s3_script_exists(self):
        assert (ROOT / "scripts" / "setup-s3.sh").is_file()

    def test_setup_s3_script_executable(self):
        path = ROOT / "scripts" / "setup-s3.sh"
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR, "setup-s3.sh must be executable by owner"


# ── setup-s3.sh content validation ─────────────────────────────────────


class TestSetupS3ScriptContent:
    SCRIPT = (ROOT / "scripts" / "setup-s3.sh").read_text()

    def test_has_bash_shebang(self):
        assert self.SCRIPT.startswith("#!/")
        assert "bash" in self.SCRIPT.splitlines()[0]

    def test_has_set_euo_pipefail(self):
        assert "set -euo pipefail" in self.SCRIPT

    def test_uses_ap_south_1_region(self):
        assert "ap-south-1" in self.SCRIPT

    def test_bucket_prefix_sehatsamjho_audio(self):
        assert "sehatsamjho-audio" in self.SCRIPT

    def test_detects_aws_account_id(self):
        assert "sts get-caller-identity" in self.SCRIPT

    def test_creates_bucket_with_create_bucket(self):
        assert "create-bucket" in self.SCRIPT

    def test_sets_location_constraint(self):
        assert "LocationConstraint" in self.SCRIPT

    def test_blocks_all_public_access(self):
        assert "put-public-access-block" in self.SCRIPT
        assert "BlockPublicAcls=true" in self.SCRIPT
        assert "IgnorePublicAcls=true" in self.SCRIPT
        assert "BlockPublicPolicy=true" in self.SCRIPT
        assert "RestrictPublicBuckets=true" in self.SCRIPT

    def test_creates_lifecycle_rule(self):
        assert "put-bucket-lifecycle-configuration" in self.SCRIPT

    def test_lifecycle_rule_id(self):
        assert "delete-audio-24h" in self.SCRIPT

    def test_lifecycle_targets_audio_prefix(self):
        assert '"Prefix": "audio/"' in self.SCRIPT or "'Prefix': 'audio/'" in self.SCRIPT

    def test_lifecycle_expiration_1_day(self):
        assert '"Days": 1' in self.SCRIPT or "'Days': 1" in self.SCRIPT

    def test_lifecycle_rule_enabled(self):
        assert '"Status": "Enabled"' in self.SCRIPT or "'Status': 'Enabled'" in self.SCRIPT

    def test_checks_bucket_exists_before_creating(self):
        assert "head-bucket" in self.SCRIPT

    def test_verifies_bucket_location(self):
        assert "get-bucket-location" in self.SCRIPT

    def test_verifies_public_access_block(self):
        assert "get-public-access-block" in self.SCRIPT

    def test_checks_no_cors(self):
        assert "get-bucket-cors" in self.SCRIPT

    def test_no_hardcoded_secrets(self):
        for keyword in ["sk-proj-", "sk-ant-api", "ACxxxxxxx", "AKIA"]:
            assert keyword not in self.SCRIPT, f"Script must not contain '{keyword}'"

    def test_outputs_s3_bucket_env_var(self):
        assert "S3_BUCKET" in self.SCRIPT

    def test_prints_completion_message(self):
        assert "complete" in self.SCRIPT.lower() or "done" in self.SCRIPT.lower()


# ── validate-s3.sh existence and permissions ───────────────────────────


class TestValidateS3ScriptExists:
    def test_validate_s3_script_exists(self):
        assert (ROOT / "scripts" / "validate-s3.sh").is_file()

    def test_validate_s3_script_executable(self):
        path = ROOT / "scripts" / "validate-s3.sh"
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR, "validate-s3.sh must be executable by owner"


# ── validate-s3.sh content validation ──────────────────────────────────


class TestValidateS3ScriptContent:
    SCRIPT = (ROOT / "scripts" / "validate-s3.sh").read_text()

    def test_has_bash_shebang(self):
        assert self.SCRIPT.startswith("#!/")
        assert "bash" in self.SCRIPT.splitlines()[0]

    def test_has_set_euo_pipefail(self):
        assert "set -euo pipefail" in self.SCRIPT

    def test_checks_bucket_exists(self):
        assert "head-bucket" in self.SCRIPT

    def test_checks_bucket_region(self):
        assert "get-bucket-location" in self.SCRIPT

    def test_checks_public_access_block(self):
        assert "get-public-access-block" in self.SCRIPT
        assert "BlockPublicAcls" in self.SCRIPT

    def test_checks_lifecycle_rule(self):
        assert "get-bucket-lifecycle-configuration" in self.SCRIPT
        assert "audio/" in self.SCRIPT

    def test_checks_no_cors(self):
        assert "get-bucket-cors" in self.SCRIPT

    def test_tests_upload(self):
        assert "s3 cp" in self.SCRIPT or "put-object" in self.SCRIPT

    def test_reports_pass_fail(self):
        assert "PASS" in self.SCRIPT or "pass" in self.SCRIPT.lower()
        assert "FAIL" in self.SCRIPT or "fail" in self.SCRIPT.lower()

    def test_exits_nonzero_on_failure(self):
        assert "exit 1" in self.SCRIPT

    def test_accepts_bucket_name_argument(self):
        """Script should accept an optional bucket name argument."""
        assert "${1:-}" in self.SCRIPT or "${1:" in self.SCRIPT or "$1" in self.SCRIPT

    def test_auto_detects_account_id_if_no_arg(self):
        assert "sts get-caller-identity" in self.SCRIPT

    def test_no_hardcoded_secrets(self):
        for keyword in ["sk-proj-", "sk-ant-api", "ACxxxxxxx", "AKIA"]:
            assert keyword not in self.SCRIPT, f"Script must not contain '{keyword}'"
