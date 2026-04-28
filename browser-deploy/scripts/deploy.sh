#!/usr/bin/env bash
# Pull latest code and restart the game server.
# Run as root on the LXC.
set -euo pipefail

DEPLOY_DIR="/opt/hackerzork/repo"
SVC_USER="hackerzork"

cd "${DEPLOY_DIR}"
sudo -u "${SVC_USER}" git pull origin main
sudo -u "${SVC_USER}" .venv/bin/pip install -r requirements.txt -q
sudo -u "${SVC_USER}" .venv/bin/pip install -r browser-deploy/server/requirements.txt -q
systemctl restart hackerzork-ws

echo "Deployed. Server restarting…"
systemctl status hackerzork-ws --no-pager
