#!/usr/bin/env bash
# ===========================================================================
# IAM Role Setup Script — SehatSamjho (S12.4)
# Creates IAM policy, role, instance profile for EC2 S3 audio access.
#
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - S12.1 complete — EC2 instance running in ap-south-1
#   - S12.3 complete — S3 bucket created
#
# Usage:
#   chmod +x scripts/setup-iam.sh
#   ./scripts/setup-iam.sh [EC2_INSTANCE_ID]
#
# The script will:
#   1. Detect AWS account ID
#   2. Create IAM policy SehatSamjhoS3AudioPolicy (PutObject, GetObject, DeleteObject)
#   3. Create IAM role SehatSamjhoEC2Role (trusted entity: ec2.amazonaws.com)
#   4. Create instance profile SehatSamjhoEC2Profile and attach role
#   5. Associate instance profile with EC2 instance
# ===========================================================================
set -euo pipefail

REGION="ap-south-1"
POLICY_NAME="SehatSamjhoS3AudioPolicy"
ROLE_NAME="SehatSamjhoEC2Role"
PROFILE_NAME="SehatSamjhoEC2Profile"

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

POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
BUCKET_ARN="arn:aws:s3:::sehatsamjho-audio-${ACCOUNT_ID}"

# ---- Step 2: Create IAM Policy ----
info "=== [2/5] Creating IAM Policy: ${POLICY_NAME} ==="

POLICY_DOCUMENT=$(cat <<'PDEOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::sehatsamjho-audio-*/*"
    }
  ]
}
PDEOF
)

if aws iam get-policy --policy-arn "$POLICY_ARN" 2>/dev/null; then
  info "Policy '${POLICY_NAME}' already exists. Skipping creation."
else
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOCUMENT" \
    --description "Allows PutObject, GetObject, DeleteObject on SehatSamjho audio bucket only"

  info "Created policy: ${POLICY_NAME}"
fi

# ---- Step 3: Create IAM Role ----
info "=== [3/5] Creating IAM Role: ${ROLE_NAME} ==="

TRUST_POLICY=$(cat <<'TPEOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
TPEOF
)

if aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
  info "Role '${ROLE_NAME}' already exists. Skipping creation."
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --description "EC2 instance role for SehatSamjho — S3 audio access only"

  info "Created role: ${ROLE_NAME}"
fi

# Attach the policy to the role (idempotent)
info "Attaching policy '${POLICY_NAME}' to role '${ROLE_NAME}'..."
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN"
info "Policy attached."

# ---- Step 4: Create Instance Profile ----
info "=== [4/5] Creating Instance Profile: ${PROFILE_NAME} ==="

if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" 2>/dev/null; then
  info "Instance profile '${PROFILE_NAME}' already exists. Skipping creation."
else
  aws iam create-instance-profile \
    --instance-profile-name "$PROFILE_NAME"

  info "Created instance profile: ${PROFILE_NAME}"
fi

# Add role to instance profile (idempotent — may error if already added)
info "Adding role '${ROLE_NAME}' to instance profile '${PROFILE_NAME}'..."
if aws iam add-role-to-instance-profile \
  --instance-profile-name "$PROFILE_NAME" \
  --role-name "$ROLE_NAME" 2>/dev/null; then
  info "Role added to instance profile."
else
  info "Role already in instance profile. Skipping."
fi

# Wait for instance profile propagation
info "Waiting 10 seconds for IAM propagation..."
sleep 10

# ---- Step 5: Associate Instance Profile with EC2 ----
info "=== [5/5] Associating Instance Profile with EC2 ==="

INSTANCE_ID="${1:-}"
if [ -z "$INSTANCE_ID" ]; then
  warn "No EC2 instance ID provided as argument."
  warn "Usage: ./scripts/setup-iam.sh i-0123456789abcdef0"
  warn "Skipping EC2 association. You can attach manually via:"
  warn "  aws ec2 associate-iam-instance-profile \\"
  warn "    --iam-instance-profile Name=${PROFILE_NAME} \\"
  warn "    --instance-id <YOUR_INSTANCE_ID>"
else
  # Check if instance already has a profile
  EXISTING_PROFILE=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query "Reservations[0].Instances[0].IamInstanceProfile.Arn" \
    --output text 2>/dev/null || echo "None")

  if [ "$EXISTING_PROFILE" != "None" ] && [ -n "$EXISTING_PROFILE" ]; then
    warn "Instance ${INSTANCE_ID} already has an IAM instance profile:"
    warn "  ${EXISTING_PROFILE}"
    warn "To replace it, first disassociate the existing profile, then re-run."
  else
    aws ec2 associate-iam-instance-profile \
      --iam-instance-profile Name="$PROFILE_NAME" \
      --instance-id "$INSTANCE_ID"

    info "Instance profile '${PROFILE_NAME}' associated with instance '${INSTANCE_ID}'."
  fi
fi

echo ""
echo "============================================="
echo " IAM Role Setup Complete!"
echo ""
echo " Policy:           ${POLICY_NAME}"
echo " Role:             ${ROLE_NAME}"
echo " Instance Profile: ${PROFILE_NAME}"
echo " Bucket ARN:       ${BUCKET_ARN}"
echo ""
echo " The policy allows ONLY:"
echo "   - s3:PutObject"
echo "   - s3:GetObject"
echo "   - s3:DeleteObject"
echo "   on arn:aws:s3:::sehatsamjho-audio-*/*"
echo ""
echo " Next steps:"
echo "   1. Remove AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from .env on EC2"
echo "   2. Restart the app: docker compose -f docker-compose.prod.yml restart app"
echo "   3. Verify: run scripts/validate-iam.sh"
echo "============================================="
