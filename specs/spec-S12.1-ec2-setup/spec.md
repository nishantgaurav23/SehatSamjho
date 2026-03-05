# Spec S12.1 — EC2 t3.micro Setup

## Overview
Provision an AWS EC2 t3.micro instance in ap-south-1 (Mumbai) region to host the SehatSamjho Docker deployment. The instance runs Ubuntu 22.04 LTS with Docker and docker compose plugin installed. Security groups restrict inbound traffic to HTTP (80), HTTPS (443), and SSH (22, locked to the developer's IP). An Elastic IP is assigned for a stable public address used by the Twilio webhook.

## Dependencies
- S11.1 (Multi-stage Dockerfile) — must be built and tested locally
- S11.3 (Docker Compose Prod) — `docker-compose.prod.yml` must exist and work locally

## Target Location
- AWS Console / CLI — no code files; output is a running EC2 instance
- Documentation artifacts: this spec serves as the runbook

---

## Functional Requirements

### FR-1: EC2 Instance Provisioning
- **What**: Launch a t3.micro instance in ap-south-1 (Mumbai)
- **AMI**: Ubuntu 22.04 LTS (latest official Canonical AMI for ap-south-1)
- **Instance type**: t3.micro (free tier eligible, 2 vCPUs, 1 GiB RAM)
- **Storage**: 20 GB gp3 root volume (free tier allows up to 30 GB)
- **Key pair**: Create or use an existing SSH key pair (`sehatsamjho-key.pem`)
- **Edge cases**: Verify free tier eligibility, check region availability

### FR-2: Security Group Configuration
- **What**: Create a security group `sehatsamjho-sg` with minimal inbound rules
- **Inbound rules**:
  - Port 22 (SSH): source = developer's current IP only (`x.x.x.x/32`)
  - Port 80 (HTTP): source = `0.0.0.0/0` (Twilio webhook traffic)
  - Port 443 (HTTPS): source = `0.0.0.0/0` (future TLS termination)
- **Outbound rules**: Allow all (default)
- **Edge cases**: SSH IP changes — document how to update the rule

### FR-3: Elastic IP Assignment
- **What**: Allocate an Elastic IP and associate it with the EC2 instance
- **Why**: Stable public IP for Twilio webhook URL (no DNS changes on reboot)
- **Cost**: Free when attached to a running instance; $0.005/hr if detached
- **Edge cases**: Release unused Elastic IPs to avoid charges

### FR-4: Docker + Docker Compose Installation
- **What**: Install Docker Engine and docker compose plugin on the EC2 instance
- **Method**: Official Docker apt repository (not snap)
- **Steps**:
  1. Update apt and install prerequisites
  2. Add Docker GPG key and repository
  3. Install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-compose-plugin`
  4. Add `ubuntu` user to `docker` group (no sudo needed for docker commands)
  5. Verify: `docker --version` and `docker compose version`
- **Edge cases**: Ensure docker service starts on boot (`systemctl enable docker`)

### FR-5: Instance Connectivity Verification
- **What**: Verify SSH access and basic instance health
- **Steps**:
  1. SSH into instance: `ssh -i sehatsamjho-key.pem ubuntu@<elastic-ip>`
  2. Verify Docker: `docker run hello-world`
  3. Verify docker compose: `docker compose version`
  4. Verify outbound internet: `curl -s https://api.ipify.org` returns the Elastic IP
- **Edge cases**: SSH timeout (check security group), Docker permission denied (check group membership)

---

## Tangible Outcomes

- [ ] **Outcome 1**: EC2 t3.micro instance running in ap-south-1 with status "running"
- [ ] **Outcome 2**: Security group `sehatsamjho-sg` has exactly 3 inbound rules (SSH/80/443)
- [ ] **Outcome 3**: Elastic IP allocated and associated with the instance
- [ ] **Outcome 4**: `docker --version` returns 24.x+ on the instance
- [ ] **Outcome 5**: `docker compose version` returns v2.x+ on the instance
- [ ] **Outcome 6**: `docker run hello-world` succeeds without sudo
- [ ] **Outcome 7**: SSH access works with the key pair from developer machine

---

## Test-Driven Requirements

### Verification Steps (Manual — AWS Console + SSH)
1. **verify_instance_region**: AWS Console shows instance in ap-south-1
2. **verify_instance_type**: Instance type is t3.micro
3. **verify_ami**: AMI is Ubuntu 22.04 LTS
4. **verify_storage**: Root volume is 20 GB gp3
5. **verify_security_group_ssh**: Port 22 open to developer IP only
6. **verify_security_group_http**: Port 80 open to 0.0.0.0/0
7. **verify_security_group_https**: Port 443 open to 0.0.0.0/0
8. **verify_elastic_ip**: Elastic IP associated, instance reachable at that IP
9. **verify_docker_installed**: `docker --version` outputs version 24+
10. **verify_compose_installed**: `docker compose version` outputs v2+
11. **verify_docker_no_sudo**: `docker run hello-world` succeeds as ubuntu user
12. **verify_ssh_access**: Can SSH from developer machine with key pair

### Mocking Strategy
- N/A — this is an infrastructure provisioning spec, not a code spec
- Verification is manual via AWS Console and SSH commands

### Coverage Expectation
- All 7 tangible outcomes verified manually before marking spec as done

---

## Runbook — Step-by-Step Commands

### Step 1: Launch EC2 Instance (AWS Console)
1. Go to EC2 Dashboard in ap-south-1
2. Click "Launch Instance"
3. Name: `sehatsamjho-app`
4. AMI: Ubuntu 22.04 LTS (64-bit x86)
5. Instance type: t3.micro
6. Key pair: Create new → `sehatsamjho-key` → Download `.pem` file
7. Network: Default VPC, auto-assign public IP = Enable
8. Security group: Create new → `sehatsamjho-sg`
   - SSH (22) from My IP
   - HTTP (80) from Anywhere
   - HTTPS (443) from Anywhere
9. Storage: 20 GiB gp3
10. Launch instance

### Step 2: Allocate and Associate Elastic IP
```bash
# AWS Console: EC2 → Elastic IPs → Allocate → Associate with sehatsamjho-app
# Or via CLI:
aws ec2 allocate-address --domain vpc --region ap-south-1
aws ec2 associate-address --instance-id <instance-id> --allocation-id <alloc-id> --region ap-south-1
```

### Step 3: SSH and Install Docker
```bash
# Secure the key file
chmod 400 sehatsamjho-key.pem

# SSH in
ssh -i sehatsamjho-key.pem ubuntu@<elastic-ip>

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker prerequisites
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Enable Docker on boot
sudo systemctl enable docker

# Log out and back in for group membership to take effect
exit
ssh -i sehatsamjho-key.pem ubuntu@<elastic-ip>

# Verify
docker --version
docker compose version
docker run hello-world
```

### Step 4: Verify Connectivity
```bash
# From developer machine — verify HTTP port is open
curl -s -o /dev/null -w "%{http_code}" http://<elastic-ip>/
# Expected: connection refused (no app yet) but port is reachable

# From EC2 — verify outbound internet
curl -s https://api.ipify.org
# Expected: <elastic-ip>
```

---

## References
- roadmap.md (Phase 12, S12.1)
- S11.1 spec (Dockerfile)
- S11.3 spec (docker-compose.prod.yml)
- AWS Free Tier: https://aws.amazon.com/free/
- Docker install on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
