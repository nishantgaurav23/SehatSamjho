#!/usr/bin/env bash
# ===========================================================================
# RDS Setup Script — SehatSamjho
# Provisions an RDS db.t3.micro PostgreSQL instance in the same VPC as EC2.
#
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - S12.1 complete — EC2 instance running with security group
#   - jq installed (sudo apt install jq)
#
# Usage:
#   chmod +x scripts/rds-setup.sh
#   ./scripts/rds-setup.sh
#
# The script will:
#   1. Detect VPC and EC2 security group from the running instance
#   2. Create an RDS security group (port 5432 from EC2 SG only)
#   3. Create a DB subnet group (2+ AZs)
#   4. Launch RDS db.t3.micro PostgreSQL 15 instance
#   5. Wait for it to become available
#   6. Output the DATABASE_URL for .env.prod
# ===========================================================================
set -euo pipefail

REGION="ap-south-1"
DB_INSTANCE_ID="sehatsamjho"
DB_NAME="sehatsamjho"
DB_USERNAME="ssadmin"
DB_INSTANCE_CLASS="db.t3.micro"
DB_ENGINE="postgres"
DB_ENGINE_VERSION="15"
DB_STORAGE_GB=20
DB_STORAGE_TYPE="gp2"
DB_BACKUP_RETENTION=7
DB_BACKUP_WINDOW="21:30-22:30"  # 03:00-04:00 IST
EC2_INSTANCE_NAME="sehatsamjho-app"
EC2_SG_NAME="sehatsamjho-sg"
RDS_SG_NAME="sehatsamjho-rds-sg"
DB_SUBNET_GROUP_NAME="sehatsamjho-db-subnet"

# ---- Colors ----
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- Step 1: Generate a strong password ----
echo ""
info "=== [1/7] Generating database password ==="
DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)
info "Password generated (24 chars, alphanumeric)"

# ---- Step 2: Find EC2 instance VPC and Security Group ----
info "=== [2/7] Detecting EC2 instance VPC and Security Group ==="

EC2_INSTANCE_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=${EC2_INSTANCE_NAME}" \
            "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

if [ "$EC2_INSTANCE_ID" = "None" ] || [ -z "$EC2_INSTANCE_ID" ]; then
  error "EC2 instance '${EC2_INSTANCE_NAME}' not found or not running in ${REGION}."
  error "Complete S12.1 first."
  exit 1
fi
info "EC2 Instance: ${EC2_INSTANCE_ID}"

VPC_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$EC2_INSTANCE_ID" \
  --query "Reservations[0].Instances[0].VpcId" \
  --output text)
info "VPC: ${VPC_ID}"

EC2_SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=group-name,Values=${EC2_SG_NAME}" \
            "Name=vpc-id,Values=${VPC_ID}" \
  --query "SecurityGroups[0].GroupId" \
  --output text)

if [ "$EC2_SG_ID" = "None" ] || [ -z "$EC2_SG_ID" ]; then
  error "EC2 security group '${EC2_SG_NAME}' not found in VPC ${VPC_ID}."
  exit 1
fi
info "EC2 Security Group: ${EC2_SG_ID}"

# ---- Step 3: Create RDS Security Group ----
info "=== [3/7] Creating RDS Security Group ==="

# Check if SG already exists
EXISTING_RDS_SG=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=group-name,Values=${RDS_SG_NAME}" \
            "Name=vpc-id,Values=${VPC_ID}" \
  --query "SecurityGroups[0].GroupId" \
  --output text 2>/dev/null || echo "None")

if [ "$EXISTING_RDS_SG" != "None" ] && [ -n "$EXISTING_RDS_SG" ]; then
  RDS_SG_ID="$EXISTING_RDS_SG"
  info "RDS Security Group already exists: ${RDS_SG_ID}"
else
  RDS_SG_ID=$(aws ec2 create-security-group \
    --region "$REGION" \
    --group-name "$RDS_SG_NAME" \
    --description "SehatSamjho RDS - port 5432 from EC2 only" \
    --vpc-id "$VPC_ID" \
    --query "GroupId" \
    --output text)

  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$RDS_SG_ID" \
    --protocol tcp \
    --port 5432 \
    --source-group "$EC2_SG_ID"

  aws ec2 create-tags \
    --region "$REGION" \
    --resources "$RDS_SG_ID" \
    --tags Key=Name,Value="$RDS_SG_NAME" Key=Project,Value=SehatSamjho

  info "Created RDS Security Group: ${RDS_SG_ID}"
  info "Inbound rule: TCP 5432 from ${EC2_SG_ID}"
fi

# ---- Step 4: Create DB Subnet Group ----
info "=== [4/7] Creating DB Subnet Group ==="

# Check if subnet group already exists
EXISTING_SUBNET_GROUP=$(aws rds describe-db-subnet-groups \
  --region "$REGION" \
  --query "DBSubnetGroups[?DBSubnetGroupName=='${DB_SUBNET_GROUP_NAME}'].DBSubnetGroupName" \
  --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_SUBNET_GROUP" ] && [ "$EXISTING_SUBNET_GROUP" != "None" ]; then
  info "DB Subnet Group already exists: ${DB_SUBNET_GROUP_NAME}"
else
  # Get all subnets in the VPC (need at least 2 AZs for RDS)
  SUBNET_IDS=$(aws ec2 describe-subnets \
    --region "$REGION" \
    --filters "Name=vpc-id,Values=${VPC_ID}" \
    --query "Subnets[*].SubnetId" \
    --output text)

  SUBNET_COUNT=$(echo "$SUBNET_IDS" | wc -w | tr -d ' ')
  if [ "$SUBNET_COUNT" -lt 2 ]; then
    error "Need at least 2 subnets in different AZs. Found ${SUBNET_COUNT}."
    exit 1
  fi

  # Convert space-separated to JSON array format
  SUBNET_ARRAY=$(echo "$SUBNET_IDS" | tr '\t' '\n' | jq -R . | jq -s .)

  aws rds create-db-subnet-group \
    --region "$REGION" \
    --db-subnet-group-name "$DB_SUBNET_GROUP_NAME" \
    --db-subnet-group-description "SehatSamjho DB subnets (2+ AZs)" \
    --subnet-ids "$SUBNET_IDS" \
    --tags Key=Project,Value=SehatSamjho

  info "Created DB Subnet Group: ${DB_SUBNET_GROUP_NAME}"
fi

# ---- Step 5: Create RDS Instance ----
info "=== [5/7] Creating RDS Instance ==="

# Check if instance already exists
EXISTING_RDS=$(aws rds describe-db-instances \
  --region "$REGION" \
  --query "DBInstances[?DBInstanceIdentifier=='${DB_INSTANCE_ID}'].DBInstanceStatus" \
  --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_RDS" ] && [ "$EXISTING_RDS" != "None" ]; then
  info "RDS instance already exists (status: ${EXISTING_RDS}). Skipping creation."
else
  aws rds create-db-instance \
    --region "$REGION" \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --db-instance-class "$DB_INSTANCE_CLASS" \
    --engine "$DB_ENGINE" \
    --engine-version "$DB_ENGINE_VERSION" \
    --master-username "$DB_USERNAME" \
    --master-user-password "$DB_PASSWORD" \
    --allocated-storage "$DB_STORAGE_GB" \
    --storage-type "$DB_STORAGE_TYPE" \
    --storage-encrypted \
    --db-name "$DB_NAME" \
    --vpc-security-group-ids "$RDS_SG_ID" \
    --db-subnet-group-name "$DB_SUBNET_GROUP_NAME" \
    --backup-retention-period "$DB_BACKUP_RETENTION" \
    --preferred-backup-window "$DB_BACKUP_WINDOW" \
    --no-publicly-accessible \
    --no-multi-az \
    --no-enable-performance-insights \
    --no-auto-minor-version-upgrade \
    --tags Key=Name,Value=SehatSamjho-RDS Key=Project,Value=SehatSamjho

  info "RDS instance creation initiated."
fi

# ---- Step 6: Wait for RDS to become available ----
info "=== [6/7] Waiting for RDS instance to become available ==="
info "This typically takes 5-10 minutes..."

aws rds wait db-instance-available \
  --region "$REGION" \
  --db-instance-identifier "$DB_INSTANCE_ID"

info "RDS instance is now available!"

# ---- Step 7: Retrieve endpoint and output connection info ----
info "=== [7/7] Retrieving RDS endpoint ==="

RDS_ENDPOINT=$(aws rds describe-db-instances \
  --region "$REGION" \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

RDS_PORT=$(aws rds describe-db-instances \
  --region "$REGION" \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].Endpoint.Port" \
  --output text)

DATABASE_URL="postgresql+asyncpg://${DB_USERNAME}:${DB_PASSWORD}@${RDS_ENDPOINT}:${RDS_PORT}/${DB_NAME}"

echo ""
echo "============================================="
echo " RDS Setup Complete!"
echo ""
echo " Instance ID:  ${DB_INSTANCE_ID}"
echo " Engine:       PostgreSQL ${DB_ENGINE_VERSION}"
echo " Class:        ${DB_INSTANCE_CLASS}"
echo " Storage:      ${DB_STORAGE_GB}GB ${DB_STORAGE_TYPE}"
echo " Endpoint:     ${RDS_ENDPOINT}:${RDS_PORT}"
echo " Database:     ${DB_NAME}"
echo " Username:     ${DB_USERNAME}"
echo " Encryption:   Enabled (AWS KMS default key)"
echo " Backups:      ${DB_BACKUP_RETENTION}-day retention"
echo " Public:       No"
echo ""
echo " Security Group: ${RDS_SG_ID}"
echo "   Inbound: TCP 5432 from EC2 SG ${EC2_SG_ID}"
echo ""
echo " DATABASE_URL (add to .env.prod on EC2):"
echo "   ${DATABASE_URL}"
echo ""
echo " Next steps:"
echo "   1. SSH to EC2 and install psql client:"
echo "      sudo apt install -y postgresql-client"
echo ""
echo "   2. Test connectivity from EC2:"
echo "      psql -h ${RDS_ENDPOINT} -U ${DB_USERNAME} -d ${DB_NAME}"
echo "      (enter password when prompted)"
echo ""
echo "   3. Add DATABASE_URL to /app/SehatSamjho/.env on EC2"
echo ""
echo "   4. Run migrations (after S12.6 deploy):"
echo "      docker compose -f docker-compose.prod.yml exec app \\"
echo "        python -m alembic -c backend/alembic.ini upgrade head"
echo ""
echo " IMPORTANT: Save this password securely!"
echo "   Password: ${DB_PASSWORD}"
echo "============================================="
