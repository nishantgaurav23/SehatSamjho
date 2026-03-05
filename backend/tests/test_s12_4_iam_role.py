"""Tests for S12.4 — IAM Role for EC2.

Static validation of infrastructure artifacts:
- scripts/setup-iam.sh (IAM policy + role + instance profile creation)
- scripts/validate-iam.sh (IAM setup validation script)
"""

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # project root


# ── setup-iam.sh existence and permissions ──────────────────────────────


class TestSetupIamScriptExists:
    def test_setup_iam_script_exists(self):
        assert (ROOT / "scripts" / "setup-iam.sh").is_file()

    def test_setup_iam_script_executable(self):
        path = ROOT / "scripts" / "setup-iam.sh"
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR, "setup-iam.sh must be executable by owner"


# ── setup-iam.sh content validation ─────────────────────────────────────


class TestSetupIamScriptContent:
    SCRIPT = (ROOT / "scripts" / "setup-iam.sh").read_text()

    def test_has_bash_shebang(self):
        assert self.SCRIPT.startswith("#!/")
        assert "bash" in self.SCRIPT.splitlines()[0]

    def test_has_set_euo_pipefail(self):
        assert "set -euo pipefail" in self.SCRIPT

    def test_detects_aws_account_id(self):
        assert "sts get-caller-identity" in self.SCRIPT

    # ── FR-1: IAM Policy ──

    def test_creates_iam_policy(self):
        assert "create-policy" in self.SCRIPT

    def test_policy_name(self):
        assert "SehatSamjhoS3AudioPolicy" in self.SCRIPT

    def test_policy_allows_put_object(self):
        assert "s3:PutObject" in self.SCRIPT

    def test_policy_allows_get_object(self):
        assert "s3:GetObject" in self.SCRIPT

    def test_policy_allows_delete_object(self):
        assert "s3:DeleteObject" in self.SCRIPT

    def test_policy_scoped_to_audio_bucket(self):
        assert "sehatsamjho-audio" in self.SCRIPT
        assert "arn:aws:s3:::" in self.SCRIPT

    def test_no_s3_wildcard_actions(self):
        """Policy must NOT use s3:* — principle of least privilege."""
        assert '"s3:*"' not in self.SCRIPT
        assert "'s3:*'" not in self.SCRIPT

    def test_no_list_bucket(self):
        """Policy should NOT include s3:ListBucket."""
        assert "s3:ListBucket" not in self.SCRIPT

    # ── FR-2: IAM Role ──

    def test_creates_iam_role(self):
        assert "create-role" in self.SCRIPT

    def test_role_name(self):
        assert "SehatSamjhoEC2Role" in self.SCRIPT

    def test_trusted_entity_ec2(self):
        assert "ec2.amazonaws.com" in self.SCRIPT

    def test_attaches_policy_to_role(self):
        assert "attach-role-policy" in self.SCRIPT

    def test_no_admin_access(self):
        """Role must NOT have AdministratorAccess."""
        assert "AdministratorAccess" not in self.SCRIPT

    def test_no_s3_full_access(self):
        """Role must NOT have AmazonS3FullAccess."""
        assert "AmazonS3FullAccess" not in self.SCRIPT

    # ── FR-3: Instance Profile ──

    def test_creates_instance_profile(self):
        assert "create-instance-profile" in self.SCRIPT

    def test_instance_profile_name(self):
        assert "SehatSamjhoEC2Profile" in self.SCRIPT

    def test_adds_role_to_instance_profile(self):
        assert "add-role-to-instance-profile" in self.SCRIPT

    def test_associates_instance_profile_to_ec2(self):
        assert "associate-iam-instance-profile" in self.SCRIPT

    # ── General ──

    def test_checks_if_policy_exists_before_creating(self):
        """Script should check if resources exist to be idempotent."""
        assert "get-policy" in self.SCRIPT

    def test_checks_if_role_exists_before_creating(self):
        assert "get-role" in self.SCRIPT

    def test_no_hardcoded_secrets(self):
        for keyword in ["sk-proj-", "sk-ant-api", "ACxxxxxxx", "AKIA"]:
            assert keyword not in self.SCRIPT, f"Script must not contain '{keyword}'"

    def test_prints_completion_message(self):
        assert "complete" in self.SCRIPT.lower() or "done" in self.SCRIPT.lower()


# ── validate-iam.sh existence and permissions ───────────────────────────


class TestValidateIamScriptExists:
    def test_validate_iam_script_exists(self):
        assert (ROOT / "scripts" / "validate-iam.sh").is_file()

    def test_validate_iam_script_executable(self):
        path = ROOT / "scripts" / "validate-iam.sh"
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR, "validate-iam.sh must be executable by owner"


# ── validate-iam.sh content validation ──────────────────────────────────


class TestValidateIamScriptContent:
    SCRIPT = (ROOT / "scripts" / "validate-iam.sh").read_text()

    def test_has_bash_shebang(self):
        assert self.SCRIPT.startswith("#!/")
        assert "bash" in self.SCRIPT.splitlines()[0]

    def test_has_set_euo_pipefail(self):
        assert "set -euo pipefail" in self.SCRIPT

    def test_verifies_policy_exists(self):
        assert "get-policy" in self.SCRIPT
        assert "SehatSamjhoS3AudioPolicy" in self.SCRIPT

    def test_verifies_policy_document(self):
        assert "get-policy-version" in self.SCRIPT

    def test_checks_policy_actions(self):
        assert "s3:PutObject" in self.SCRIPT
        assert "s3:GetObject" in self.SCRIPT
        assert "s3:DeleteObject" in self.SCRIPT

    def test_verifies_role_exists(self):
        assert "get-role" in self.SCRIPT
        assert "SehatSamjhoEC2Role" in self.SCRIPT

    def test_checks_trusted_entity(self):
        assert "ec2.amazonaws.com" in self.SCRIPT

    def test_verifies_attached_policies(self):
        assert "list-attached-role-policies" in self.SCRIPT

    def test_checks_exactly_one_policy_attached(self):
        """Validation should verify only 1 policy is attached to the role."""
        assert "AttachedPolicies" in self.SCRIPT

    def test_verifies_instance_profile(self):
        assert "SehatSamjhoEC2Profile" in self.SCRIPT

    def test_reports_pass_fail(self):
        assert "PASS" in self.SCRIPT or "pass" in self.SCRIPT.lower()
        assert "FAIL" in self.SCRIPT or "fail" in self.SCRIPT.lower()

    def test_exits_nonzero_on_failure(self):
        assert "exit 1" in self.SCRIPT

    def test_no_hardcoded_secrets(self):
        for keyword in ["sk-proj-", "sk-ant-api", "ACxxxxxxx", "AKIA"]:
            assert keyword not in self.SCRIPT, f"Script must not contain '{keyword}'"

    def test_detects_aws_account_id(self):
        assert "sts get-caller-identity" in self.SCRIPT
