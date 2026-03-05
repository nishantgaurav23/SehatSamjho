#!/usr/bin/env bash
# ===========================================================================
# EC2 Bootstrap Script — SehatSamjho
# Run once on a fresh Ubuntu 22.04 EC2 instance to install Docker,
# docker compose, and prepare the deployment directory.
#
# Usage:
#   scp -i sehatsamjho-key.pem scripts/ec2-setup.sh ubuntu@<ELASTIC_IP>:~
#   ssh -i sehatsamjho-key.pem ubuntu@<ELASTIC_IP>
#   chmod +x ec2-setup.sh && ./ec2-setup.sh
# ===========================================================================
set -euo pipefail

echo "=== [1/7] Updating system packages ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== [2/7] Installing Docker prerequisites ==="
sudo apt-get install -y ca-certificates curl gnupg

echo "=== [3/7] Adding Docker GPG key and repository ==="
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "=== [4/7] Installing Docker Engine + Compose plugin ==="
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "=== [5/7] Configuring Docker for non-root use ==="
sudo usermod -aG docker "$USER"
sudo systemctl enable docker
sudo systemctl start docker

echo "=== [6/7] Creating app directory ==="
sudo mkdir -p /app
sudo chown "$USER":"$USER" /app

echo "=== [7/7] Verifying installation ==="
# Run docker commands via sudo since group membership requires re-login
sudo docker --version
sudo docker compose version
sudo docker run --rm hello-world

echo ""
echo "============================================="
echo " EC2 setup complete!"
echo ""
echo " IMPORTANT: Log out and back in for docker"
echo " group membership to take effect, then run:"
echo ""
echo "   docker --version"
echo "   docker compose version"
echo ""
echo " Next steps:"
echo "   1. Clone your repo into /app:"
echo "      cd /app && git clone git@github.com:<owner>/SehatSamjho.git ."
echo "   2. Create /app/.env with production secrets"
echo "   3. Set up GitHub Actions secrets (see deploy.yml)"
echo "============================================="
