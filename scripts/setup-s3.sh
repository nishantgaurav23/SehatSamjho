#!/usr/bin/env bash
# ===========================================================================
# S3 Bucket Setup Script — SehatSamjho
# Creates and configures an S3 bucket for TTS audio and prescription image storage.
#
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - S12.1 complete — EC2 instance running in ap-south-1
#
# Usage:
#   chmod +x scripts/setup-s3.sh
#   ./scripts/setup-s3.sh
#
# The script will:
#   1. Detect AWS account ID
#   2. Create S3 bucket sehatsamjho-audio-{account_id} in ap-south-1
#   3. Block all public access
#   4. Create lifecycle rule to delete audio/ objects after 24 hours
#   5. Verify the setup
#   6. Output S3_BUCKET value for .env.prod
# ===========================================================================
set -euo pipefail

REGION="ap-south-1"
BUCKET_PREFIX="sehatsamjho-audio"
LIFECYCLE_RULE_ID_AUDIO="delete-audio-24h"
LIFECYCLE_RULE_ID_PRESCRIPTIONS="delete-prescriptions-30d"
AUDIO_PREFIX="audio/"
PRESCRIPTIONS_PREFIX="prescriptions/"

# ---- Colors ----
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- Step 1: Detect AWS Account ID ----
echo ""
info "=== [1/5] Detecting AWS Account ID ==="

ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
  error "Could not determine AWS account ID. Check 'aws configure'."
  exit 1
fi
info "AWS Account ID: ${ACCOUNT_ID}"

BUCKET_NAME="${BUCKET_PREFIX}-${ACCOUNT_ID}"
info "Bucket name: ${BUCKET_NAME}"

# ---- Step 2: Create S3 Bucket ----
info "=== [2/5] Creating S3 Bucket ==="

# Check if bucket already exists
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
  info "Bucket '${BUCKET_NAME}' already exists. Skipping creation."
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"

  info "Created bucket: ${BUCKET_NAME}"
fi

# ---- Step 3: Block All Public Access ----
info "=== [3/5] Blocking all public access ==="

aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

info "All public access blocked."

# ---- Step 4: Create Lifecycle Rules ----
info "=== [4/5] Creating lifecycle rules ==="

LIFECYCLE_CONFIG=$(cat <<'LCEOF'
{
  "Rules": [
    {
      "ID": "delete-audio-24h",
      "Filter": {
        "Prefix": "audio/"
      },
      "Status": "Enabled",
      "Expiration": {
        "Days": 1
      }
    },
    {
      "ID": "delete-prescriptions-30d",
      "Filter": {
        "Prefix": "prescriptions/"
      },
      "Status": "Enabled",
      "Expiration": {
        "Days": 30
      }
    }
  ]
}
LCEOF
)

aws s3api put-bucket-lifecycle-configuration \
  --bucket "$BUCKET_NAME" \
  --lifecycle-configuration "$LIFECYCLE_CONFIG"

info "Lifecycle rules created:"
info "  - objects under '${AUDIO_PREFIX}' expire after 1 day"
info "  - objects under '${PRESCRIPTIONS_PREFIX}' expire after 30 days"

# ---- Step 5: Verify Setup ----
info "=== [5/5] Verifying setup ==="

# Verify bucket location
LOCATION=$(aws s3api get-bucket-location \
  --bucket "$BUCKET_NAME" \
  --query "LocationConstraint" \
  --output text)
info "Bucket region: ${LOCATION}"

# Verify public access block
PUBLIC_BLOCK=$(aws s3api get-public-access-block \
  --bucket "$BUCKET_NAME" \
  --query "PublicAccessBlockConfiguration" \
  --output json)
info "Public access block: ${PUBLIC_BLOCK}"

# Verify lifecycle
LIFECYCLE=$(aws s3api get-bucket-lifecycle-configuration \
  --bucket "$BUCKET_NAME" \
  --query "Rules" \
  --output json)
info "Lifecycle rules: ${LIFECYCLE}"

# Verify no CORS
if aws s3api get-bucket-cors --bucket "$BUCKET_NAME" 2>/dev/null; then
  warn "CORS configuration found — this is unexpected. Remove it if not needed."
else
  info "No CORS configuration (expected)."
fi

echo ""
echo "============================================="
echo " S3 Bucket Setup Complete!"
echo ""
echo " Bucket:     ${BUCKET_NAME}"
echo " Region:     ${REGION}"
echo " Public:     Blocked (all four toggles)"
echo " Lifecycle:  audio/ expires in 1 day, prescriptions/ expires in 30 days"
echo " CORS:       None (presigned URLs only)"
echo ""
echo " S3_BUCKET (add to .env.prod on EC2):"
echo "   S3_BUCKET=${BUCKET_NAME}"
echo ""
echo " Test presigned URL generation:"
echo "   aws s3api put-object --bucket ${BUCKET_NAME} --key audio/test.ogg --body /dev/null"
echo "   aws s3 presign s3://${BUCKET_NAME}/audio/test.ogg --expires-in 3600"
echo ""
echo " Next steps:"
echo "   1. Add S3_BUCKET=${BUCKET_NAME} to .env.prod on EC2"
echo "   2. Run S12.4 (IAM role) to grant EC2 access to this bucket"
echo "============================================="
