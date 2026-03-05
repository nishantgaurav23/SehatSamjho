# Checklist — Spec S12.2: RDS Setup

## Phase 1: Prerequisites
- [x] Verify S12.1 (EC2 setup) is complete — EC2 running, VPC and security group exist
- [x] Note the VPC ID and EC2 security group ID from S12.1
- [x] Identify at least 2 subnets in different AZs within the VPC
- [x] Created `scripts/rds-setup.sh` — automated AWS CLI provisioning script

## Phase 2: Security Group (automated by `scripts/rds-setup.sh`)
- [x] Create security group `sehatsamjho-rds-sg` in the same VPC
- [x] Add inbound rule: TCP port 5432, source = EC2 security group ID
- [x] Verify no other inbound rules exist

## Phase 3: DB Subnet Group (automated by `scripts/rds-setup.sh`)
- [x] Create a DB subnet group with subnets in at least 2 AZs in ap-south-1
- [x] Associate it with the same VPC as EC2

## Phase 4: RDS Instance (automated by `scripts/rds-setup.sh`)
- [x] Create RDS instance via Console or CLI:
  - Engine: PostgreSQL 15.x
  - Instance class: db.t3.micro
  - Storage: 20GB gp2
  - DB name: `sehatsamjho`
  - Master username: `ssadmin`
  - Master password: generate strong password
  - VPC: same as EC2
  - DB subnet group: from Phase 3
  - Security group: `sehatsamjho-rds-sg`
  - Public access: No
  - Backup retention: 7 days
  - Storage encryption: Enabled
  - Multi-AZ: No
  - Performance Insights: Disabled
  - Enhanced monitoring: Disabled
- [x] Wait for instance status to become `available`

## Phase 5: Connection Verification
- [ ] SSH into EC2
- [ ] Install psql client if needed: `sudo apt install -y postgresql-client`
- [ ] Test connection: `psql -h {rds_endpoint} -U ssadmin -d sehatsamjho`
- [ ] Verify connection from local machine is rejected (timeout)

## Phase 6: Application Configuration
- [ ] Construct DATABASE_URL: `postgresql+asyncpg://ssadmin:{password}@{rds_endpoint}:5432/sehatsamjho`
- [ ] Add DATABASE_URL to `.env.prod` on EC2
- [ ] Verify app can start and `/health` returns ok (after S12.6 deployment)
- [ ] Run `alembic upgrade head` to create tables (after S12.6 deployment)

## Phase 7: Final Verification
- [ ] RDS instance status: `available`
- [ ] Security group has exactly 1 inbound rule (port 5432 from EC2 SG)
- [ ] Automated backups show 7-day retention
- [ ] Storage encryption: enabled
- [ ] No public accessibility
- [ ] EC2 can connect, external IPs cannot
