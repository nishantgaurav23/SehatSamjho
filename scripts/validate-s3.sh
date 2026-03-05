#!/usr/bin/env bash
# ===========================================================================
# S3 Bucket Validation Script — SehatSamjho
# Validates that the S3 bucket is correctly configured per S12.3 spec.
#
# Usage:
#   chmod +x scripts/validate-s3.sh
#   ./scripts/validate-s3.sh [bucket-name]
#
# If no bucket name is provided, it auto-detects using AWS account ID.
# ===========================================================================
set -euo pipefail

REGION="ap-south-1"
PASSED=0
FAILED=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $*"; PASSED=$((PASSED + 1)); }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILED=$((FAILED + 1)); }

# Determine bucket name
if [ -n "${1:-}" ]; then
  BUCKET_NAME="$1"
else
  ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
  BUCKET_NAME="sehatsamjho-audio-${ACCOUNT_ID}"
fi

echo "Validating S3 bucket: ${BUCKET_NAME}"
echo "============================================="

# Test 1: Bucket exists
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
  pass "Bucket exists"
else
  fail "Bucket does not exist"
fi

# Test 2: Bucket region
LOCATION=$(aws s3api get-bucket-location --bucket "$BUCKET_NAME" --query "LocationConstraint" --output text 2>/dev/null || echo "UNKNOWN")
if [ "$LOCATION" = "$REGION" ]; then
  pass "Bucket region is ${REGION}"
else
  fail "Bucket region is '${LOCATION}', expected '${REGION}'"
fi

# Test 3: Public access blocked (all four)
BLOCK_JSON=$(aws s3api get-public-access-block --bucket "$BUCKET_NAME" --query "PublicAccessBlockConfiguration" --output json 2>/dev/null || echo "{}")
BLOCK_PUBLIC_ACLS=$(echo "$BLOCK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('BlockPublicAcls', False))")
IGNORE_PUBLIC_ACLS=$(echo "$BLOCK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('IgnorePublicAcls', False))")
BLOCK_PUBLIC_POLICY=$(echo "$BLOCK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('BlockPublicPolicy', False))")
RESTRICT_PUBLIC=$(echo "$BLOCK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('RestrictPublicBuckets', False))")

if [ "$BLOCK_PUBLIC_ACLS" = "True" ] && [ "$IGNORE_PUBLIC_ACLS" = "True" ] && \
   [ "$BLOCK_PUBLIC_POLICY" = "True" ] && [ "$RESTRICT_PUBLIC" = "True" ]; then
  pass "All four public access blocks enabled"
else
  fail "Not all public access blocks enabled: BlockPublicAcls=${BLOCK_PUBLIC_ACLS}, IgnorePublicAcls=${IGNORE_PUBLIC_ACLS}, BlockPublicPolicy=${BLOCK_PUBLIC_POLICY}, RestrictPublicBuckets=${RESTRICT_PUBLIC}"
fi

# Test 4: Lifecycle rule
LIFECYCLE_JSON=$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET_NAME" --output json 2>/dev/null || echo '{"Rules":[]}')
RULE_PREFIX=$(echo "$LIFECYCLE_JSON" | python3 -c "import sys,json; r=json.load(sys.stdin)['Rules']; print(r[0].get('Filter',{}).get('Prefix','') if r else '')")
RULE_DAYS=$(echo "$LIFECYCLE_JSON" | python3 -c "import sys,json; r=json.load(sys.stdin)['Rules']; print(r[0].get('Expiration',{}).get('Days',0) if r else 0)")
RULE_STATUS=$(echo "$LIFECYCLE_JSON" | python3 -c "import sys,json; r=json.load(sys.stdin)['Rules']; print(r[0].get('Status','') if r else '')")

if [ "$RULE_PREFIX" = "audio/" ] && [ "$RULE_DAYS" = "1" ] && [ "$RULE_STATUS" = "Enabled" ]; then
  pass "Lifecycle rule: audio/ prefix, 1-day expiration, enabled"
else
  fail "Lifecycle rule incorrect: prefix='${RULE_PREFIX}', days='${RULE_DAYS}', status='${RULE_STATUS}'"
fi

# Test 5: No CORS
if aws s3api get-bucket-cors --bucket "$BUCKET_NAME" 2>/dev/null; then
  fail "CORS configuration exists (should not)"
else
  pass "No CORS configuration"
fi

# Test 6: Upload/download test
TEST_KEY="audio/validation-test-$(date +%s).txt"
echo "validation-test" > /tmp/s3-validation-test.txt
if aws s3 cp /tmp/s3-validation-test.txt "s3://${BUCKET_NAME}/${TEST_KEY}" --region "$REGION" >/dev/null 2>&1; then
  pass "Upload to audio/ prefix succeeded"
  # Clean up
  aws s3 rm "s3://${BUCKET_NAME}/${TEST_KEY}" --region "$REGION" >/dev/null 2>&1 || true
else
  fail "Upload to audio/ prefix failed"
fi
rm -f /tmp/s3-validation-test.txt

echo ""
echo "============================================="
echo " Results: ${PASSED} passed, ${FAILED} failed"
echo "============================================="

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
