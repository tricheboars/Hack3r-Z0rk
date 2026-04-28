#!/usr/bin/env bash
# Provision a fresh Debian 12 LXC for H@ck3r-Z0rk.
# Run as root inside the container.
set -euo pipefail

REPO_URL="https://github.com/tricheboars/Hack3r-Z0rk"
DEPLOY_DIR="/opt/hackerzork/repo"
SVC_USER="hackerzork"

# ── System packages ───────────────────────────────────────────────────────────
apt update && apt upgrade -y
apt install -y \
  git python3 python3-venv python3-pip \
  nginx curl wget htop sudo \
  build-essential libssl-dev

# ── SSH key auth for Patrick ──────────────────────────────────────────────────
mkdir -p /root/.ssh
chmod 700 /root/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIwuIkSuY4u374KNMo3nc1MguVWcmaGg4+C2BAk2d3VA patrick-proxmox" >> /root/.ssh/authorized_keys
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPJz0MdftlGtlng8R0glVVYC8EaU+COVW3y2qw1lWzu7 patrick@macbook" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys 2>/dev/null || true
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# ── Deployment user + directory ───────────────────────────────────────────────
mkdir -p /opt/hackerzork
useradd -r -s /usr/sbin/nologin -d /opt/hackerzork "${SVC_USER}" || true
chown "${SVC_USER}:${SVC_USER}" /opt/hackerzork

# ── Clone repo ────────────────────────────────────────────────────────────────
if [ -d "${DEPLOY_DIR}/.git" ]; then
  echo "Repo already cloned — pulling latest…"
  sudo -u "${SVC_USER}" git -C "${DEPLOY_DIR}" pull origin main
else
  sudo -u "${SVC_USER}" git clone "${REPO_URL}" "${DEPLOY_DIR}"
fi

# ── Python venv + dependencies ────────────────────────────────────────────────
cd "${DEPLOY_DIR}"
sudo -u "${SVC_USER}" python3 -m venv .venv
sudo -u "${SVC_USER}" .venv/bin/pip install --upgrade pip -q
sudo -u "${SVC_USER}" .venv/bin/pip install -e . -q
sudo -u "${SVC_USER}" .venv/bin/pip install -r browser-deploy/server/requirements.txt -q

# ── nginx ─────────────────────────────────────────────────────────────────────
cp "${DEPLOY_DIR}/browser-deploy/nginx/hackerzork.conf" \
   /etc/nginx/sites-available/hackerzork
ln -sf /etc/nginx/sites-available/hackerzork \
       /etc/nginx/sites-enabled/hackerzork
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx

# ── systemd service ───────────────────────────────────────────────────────────
cp "${DEPLOY_DIR}/browser-deploy/systemd/hackerzork-ws.service" \
   /etc/systemd/system/hackerzork-ws.service
systemctl daemon-reload
systemctl enable --now hackerzork-ws

echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "  H@ck3r-Z0rk provisioned."
echo ""
echo "  WebSocket server : systemctl status hackerzork-ws"
echo "  nginx            : systemctl status nginx"
echo "  Game URL         : http://$(hostname -I | awk '{print $1}')/"
echo "─────────────────────────────────────────────────────────────────"
