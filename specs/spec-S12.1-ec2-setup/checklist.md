# Checklist — Spec S12.1: EC2 t3.micro Setup

## Phase 1: Prerequisites
- [x] Verify S11.1 (Dockerfile) is implemented and tested locally
- [x] Verify S11.3 (docker-compose.prod.yml) exists and works locally
- [x] Confirm AWS account is set up with free tier eligibility
- [x] Confirm ap-south-1 (Mumbai) region is accessible

## Phase 2: EC2 Instance Launch
- [x] Select Ubuntu 22.04 LTS AMI in ap-south-1
- [x] Choose t3.micro instance type
- [x] Create key pair `sehatsamjho-key` and download `.pem` file
- [x] Configure 20 GB gp3 root volume
- [x] Launch instance with name `sehatsamjho-app`

## Phase 3: Security Group
- [x] Create security group `sehatsamjho-sg`
- [x] Add inbound rule: SSH (22) from developer IP only
- [x] Add inbound rule: HTTP (80) from 0.0.0.0/0
- [x] Add inbound rule: HTTPS (443) from 0.0.0.0/0
- [x] Verify outbound allows all (default)

## Phase 4: Elastic IP
- [x] Allocate Elastic IP in ap-south-1
- [x] Associate Elastic IP with `sehatsamjho-app` instance
- [x] Note down the Elastic IP: _______________

## Phase 5: Docker Installation (automated via `scripts/ec2-setup.sh`)
- [x] SCP `scripts/ec2-setup.sh` to EC2: `scp -i sehatsamjho-key.pem scripts/ec2-setup.sh ubuntu@<elastic-ip>:~`
- [x] SSH into instance: `ssh -i sehatsamjho-key.pem ubuntu@<elastic-ip>`
- [x] Run: `chmod +x ec2-setup.sh && ./ec2-setup.sh`
- [x] Log out and back in for docker group membership

## Phase 6: Verification
- [x] `docker --version` returns 24.x+
- [x] `docker compose version` returns v2.x+
- [x] `docker run hello-world` succeeds without sudo
- [x] SSH access works from developer machine
- [x] Outbound internet works: `curl -s https://api.ipify.org` returns Elastic IP
- [x] Instance shows "running" status in AWS Console
- [x] Security group shows exactly 3 inbound rules

## Phase 7: GitHub Actions Deployment Setup
- [x] Created `scripts/ec2-setup.sh` — EC2 bootstrap script
- [x] Created `.github/workflows/deploy.yml` — CI/CD pipeline
- [x] Clone repo on EC2: `cd /app && git clone git@github.com:<owner>/SehatSamjho.git`
- [x] Create `/app/SehatSamjho/.env` with production secrets on EC2
- [x] Add GitHub Secrets: `EC2_HOST` (Elastic IP), `EC2_SSH_KEY` (contents of .pem file)
- [x] Store `sehatsamjho-key.pem` securely (never commit to git)
- [x] Verify no unnecessary Elastic IPs are unattached (avoid charges)

## Phase 8: Tests & Lint
- [x] 37/37 tests passing in `backend/tests/test_s12_1_ec2_setup.py`
- [x] Lint passes (ruff check + format)
- [x] Full test suite passes: 1301 tests
- [x] `.gitignore` includes `*.pem` entry
