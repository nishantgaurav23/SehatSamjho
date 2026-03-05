# Spec S12.2 — RDS Setup

## Overview
Provision an AWS RDS db.t3.micro PostgreSQL instance in the same VPC as the EC2 instance (ap-south-1). The database will store only interaction metadata (zero PHI). Security group restricts access to the EC2 instance only. Automated backups enabled for 7 days.

## Dependencies
- S12.1 (EC2 t3.micro setup) — VPC, subnet, and EC2 security group must exist

## Target Location
AWS Console / docs (no code files — infrastructure provisioning)

---

## Functional Requirements

### FR-1: RDS Instance Creation
- **What**: Create an RDS PostgreSQL instance using the free-tier eligible db.t3.micro class
- **Inputs**: AWS Console or CLI
- **Outputs**: Running RDS instance with a publicly resolvable endpoint
- **Details**:
  - Engine: PostgreSQL 15.x (latest minor version)
  - Instance class: db.t3.micro (free tier: 750 hrs/month, 12 months)
  - Storage: 20GB gp2 (General Purpose SSD)
  - Region: ap-south-1 (Mumbai)
  - Multi-AZ: No (not needed for prototype, saves cost)
  - Database name: `sehatsamjho`
  - Master username: `ssadmin`
  - Master password: strong, stored in `.env.prod` as part of DATABASE_URL

### FR-2: VPC and Subnet Configuration
- **What**: Place the RDS instance in the same VPC as the EC2 instance
- **Inputs**: VPC ID and subnet IDs from S12.1
- **Outputs**: RDS instance accessible from EC2 within the VPC
- **Details**:
  - Use a DB subnet group spanning at least 2 availability zones in ap-south-1
  - Public accessibility: No (accessed only from EC2 within VPC)
  - If using default VPC, create a DB subnet group from existing subnets

### FR-3: Security Group
- **What**: Create a dedicated security group for the RDS instance
- **Inputs**: EC2 security group ID from S12.1
- **Outputs**: Security group allowing only EC2 to connect on port 5432
- **Details**:
  - Name: `sehatsamjho-rds-sg`
  - Inbound rule: TCP port 5432 from EC2 security group ID only
  - No other inbound rules (no public access)
  - Outbound: default (all traffic allowed)

### FR-4: Automated Backups
- **What**: Enable automated daily backups with 7-day retention
- **Inputs**: RDS configuration
- **Outputs**: Daily snapshots retained for 7 days
- **Details**:
  - Backup retention period: 7 days
  - Backup window: low-traffic window (e.g., 03:00-04:00 IST / 21:30-22:30 UTC)
  - Storage autoscaling: disabled (20GB is sufficient for prototype metadata)

### FR-5: Connection String
- **What**: Construct the DATABASE_URL for the application
- **Inputs**: RDS endpoint, port, database name, credentials
- **Outputs**: A valid async PostgreSQL connection string
- **Details**:
  - Format: `postgresql+asyncpg://ssadmin:{password}@{rds_endpoint}:5432/sehatsamjho`
  - Store in `.env.prod` on EC2 (never commit to repo)
  - Verify connectivity from EC2: `psql -h {rds_endpoint} -U ssadmin -d sehatsamjho`

### FR-6: Performance and Encryption Settings
- **What**: Configure encryption and basic performance settings
- **Inputs**: RDS configuration
- **Outputs**: Encrypted storage, appropriate parameter group
- **Details**:
  - Storage encryption: enabled (uses default AWS KMS key, no extra cost)
  - Performance Insights: disabled (not free tier)
  - Enhanced monitoring: disabled (not free tier)
  - Parameter group: default PostgreSQL 15 (no custom tuning needed for prototype)

---

## Tangible Outcomes

- [ ] **Outcome 1**: RDS instance `sehatsamjho` is in `available` state in ap-south-1
- [ ] **Outcome 2**: Security group `sehatsamjho-rds-sg` allows port 5432 only from EC2 security group
- [ ] **Outcome 3**: `psql` from EC2 can connect to the RDS endpoint on port 5432
- [ ] **Outcome 4**: `psql` from any other IP (e.g., local machine) is rejected
- [ ] **Outcome 5**: Automated backups show retention period of 7 days in RDS console
- [ ] **Outcome 6**: DATABASE_URL in `.env.prod` uses `postgresql+asyncpg://` scheme and connects successfully
- [ ] **Outcome 7**: Storage encryption is enabled on the RDS instance
- [ ] **Outcome 8**: `alembic upgrade head` runs successfully against the RDS instance (via docker compose exec)

---

## Test-Driven Requirements

### Verification Steps (Manual — Infrastructure)
1. **verify_rds_running**: AWS Console > RDS > Instances > `sehatsamjho` shows status `available`
2. **verify_engine_version**: Engine is PostgreSQL 15.x
3. **verify_instance_class**: Instance class is db.t3.micro
4. **verify_storage**: Allocated storage is 20GB gp2
5. **verify_vpc**: RDS is in the same VPC as EC2
6. **verify_no_public_access**: Publicly Accessible = No
7. **verify_security_group**: Inbound rules show only port 5432 from EC2 SG
8. **verify_backup_retention**: Backup retention = 7 days
9. **verify_encryption**: Storage encryption = Enabled
10. **verify_ec2_connectivity**: From EC2: `psql -h {endpoint} -U ssadmin -d sehatsamjho` succeeds
11. **verify_external_blocked**: From local machine: connection to RDS endpoint times out
12. **verify_database_url**: App starts with DATABASE_URL pointing to RDS and `/health` returns ok
13. **verify_alembic**: `alembic upgrade head` creates `interaction_log` table on RDS

### Mocking Strategy
- N/A — this is infrastructure provisioning, not application code
- Existing application tests continue to use mocked database connections

### Coverage Expectation
- All 13 verification steps pass manually after provisioning

---

## References
- roadmap.md (Phase 12, S12.2)
- S12.1 spec (EC2 setup — VPC, security group, Elastic IP)
- AWS RDS Free Tier: https://aws.amazon.com/rds/free/
- backend/app/core/config.py (DATABASE_URL field)
- backend/app/db/database.py (async SQLAlchemy engine using DATABASE_URL)
