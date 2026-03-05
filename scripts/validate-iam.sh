#!/usr/bin/env bash
# ===========================================================================
# IAM Role Validation Script — SehatSamjho (S12.4)
# Validates that the IAM policy, role, and instance profile are correctly
# configured for EC2 S3 audio access.
#
# Prerequisites:
#   - AWS CLI v2 installed and configured
#   - scripts/setup-iam.sh has been run
#
# Usage:
#   chmod +x scripts/validate-iam.sh
#   ./scripts/validate-iam.sh [EC2_INSTANCE_ID]
# ===========================================================================
set -euo pipefail

POLICY_NAME="SehatSamjhoS3AudioPolicy"
ROLE_NAME="SehatSamjhoEC2Role"
PROFILE_NAME="SehatSamjhoEC2Profile"

# ---- Colors ----
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

pass() { echo -e "${GREEN}[PASS]${NC} $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

# ---- Detect AWS Account ID ----
echo ""
info "Detecting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
  fail "Could not determine AWS account ID"
  echo ""
  echo "RESULT: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
  exit 1
fi
info "AWS Account ID: ${ACCOUNT_ID}"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

echo ""
info "=== Validating IAM Setup ==="

# ---- Check 1: Policy exists ----
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  pass "Policy '${POLICY_NAME}' exists"
else
  fail "Policy '${POLICY_NAME}' not found"
fi

# ---- Check 2: Policy document has correct actions ----
POLICY_VERSION=$(aws iam get-policy \
  --policy-arn "$POLICY_ARN" \
  --query "Policy.DefaultVersionId" \
  --output text 2>/dev/null || echo "NONE")

if [ "$POLICY_VERSION" != "NONE" ]; then
  POLICY_DOC=$(aws iam get-policy-version \
    --policy-arn "$POLICY_ARN" \
    --version-id "$POLICY_VERSION" \
    --query "PolicyVersion.Document" \
    --output json 2>/dev/null || echo "{}")

  # Check for required actions
  HAS_PUT=$(echo "$POLICY_DOC" | grep -c "s3:PutObject" || true)
  HAS_GET=$(echo "$POLICY_DOC" | grep -c "s3:GetObject" || true)
  HAS_DELETE=$(echo "$POLICY_DOC" | grep -c "s3:DeleteObject" || true)

  if [ "$HAS_PUT" -gt 0 ] && [ "$HAS_GET" -gt 0 ] && [ "$HAS_DELETE" -gt 0 ]; then
    pass "Policy has all 3 required S3 actions (s3:PutObject, s3:GetObject, s3:DeleteObject)"
  else
    fail "Policy missing required S3 actions"
  fi

  # Check resource is scoped to audio bucket
  HAS_AUDIO_BUCKET=$(echo "$POLICY_DOC" | grep -c "sehatsamjho-audio" || true)
  if [ "$HAS_AUDIO_BUCKET" -gt 0 ]; then
    pass "Policy resource scoped to sehatsamjho-audio bucket"
  else
    fail "Policy resource NOT scoped to sehatsamjho-audio bucket"
  fi
else
  fail "Could not retrieve policy version"
fi

# ---- Check 3: Role exists with EC2 trust ----
ROLE_DOC=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query "Role.AssumeRolePolicyDocument" \
  --output json 2>/dev/null || echo "{}")

if echo "$ROLE_DOC" | grep -q "ec2.amazonaws.com"; then
  pass "Role '${ROLE_NAME}' exists with ec2.amazonaws.com trust"
else
  fail "Role '${ROLE_NAME}' missing or wrong trust entity"
fi

# ---- Check 4: Exactly 1 policy attached to role ----
ATTACHED=$(aws iam list-attached-role-policies \
  --role-name "$ROLE_NAME" \
  --query "AttachedPolicies" \
  --output json 2>/dev/null || echo "[]")

POLICY_COUNT=$(echo "$ATTACHED" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$POLICY_COUNT" = "1" ]; then
  pass "Exactly 1 policy attached to role (least privilege)"
else
  fail "Expected 1 policy attached to role, found ${POLICY_COUNT}"
fi

# ---- Check 5: Correct policy is attached ----
ATTACHED_ARN=$(echo "$ATTACHED" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['PolicyArn'] if d else '')" 2>/dev/null || echo "")

if echo "$ATTACHED_ARN" | grep -q "$POLICY_NAME"; then
  pass "Correct policy '${POLICY_NAME}' is attached to role"
else
  fail "Wrong policy attached: ${ATTACHED_ARN}"
fi

# ---- Check 6: Instance profile exists ----
if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  pass "Instance profile '${PROFILE_NAME}' exists"
else
  fail "Instance profile '${PROFILE_NAME}' not found"
fi

# ---- Check 7: Instance profile has role ----
PROFILE_ROLES=$(aws iam get-instance-profile \
  --instance-profile-name "$PROFILE_NAME" \
  --query "InstanceProfile.Roles[].RoleName" \
  --output text 2>/dev/null || echo "")

if echo "$PROFILE_ROLES" | grep -q "$ROLE_NAME"; then
  pass "Instance profile has role '${ROLE_NAME}'"
else
  fail "Instance profile missing role '${ROLE_NAME}'"
fi

# ---- Check 8: EC2 instance has profile (optional) ----
INSTANCE_ID="${1:-}"
if [ -n "$INSTANCE_ID" ]; then
  INSTANCE_PROFILE=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query "Reservations[0].Instances[0].IamInstanceProfile.Arn" \
    --output text 2>/dev/null || echo "None")

  if echo "$INSTANCE_PROFILE" | grep -q "$PROFILE_NAME"; then
    pass "EC2 instance ${INSTANCE_ID} has profile '${PROFILE_NAME}'"
  else
    fail "EC2 instance ${INSTANCE_ID} does NOT have profile '${PROFILE_NAME}'"
  fi
else
  info "No EC2 instance ID provided — skipping instance association check"
fi

# ---- Summary ----
echo ""
echo "============================================="
echo " IAM Validation Summary"
echo " PASS: ${PASS_COUNT}"
echo " FAIL: ${FAIL_COUNT}"
echo "============================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
