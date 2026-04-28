# Spec 05 — Proxmox LXC Provisioning

## Overview

A minimal Debian 12 LXC container on Proxmox 2. The game server is a single
Python process — resource requirements are very light.

## Container Spec

| Parameter | Value |
|-----------|-------|
| Template  | `debian-12-standard` |
| Cores     | 1 |
| RAM       | 512 MB (1024 MB max) |
| Disk      | 8 GB |
| Network   | DHCP on vmbr0 (set a DHCP reservation in your router) |
| Hostname  | `hackerzork` |
| User      | unprivileged container |

## Step-by-Step: Create the LXC

### In Proxmox web UI

1. Download template: **Datacenter → pve → local → CT Templates → Templates**
   → search "debian-12" → download
2. **Create CT** button → fill in:
   - ID: pick any free CTID (e.g. 200)
   - Hostname: `hackerzork`
   - Password: set a root password (or skip — SSH key only below)
   - Template: debian-12-standard
   - Disk: 8GB on local-lvm
   - CPU: 1 core
   - Memory: 512 MB, Swap: 512 MB
   - Network: DHCP, bridge vmbr0
3. Start the container

### Or via pct CLI on Proxmox host

```bash
pct create 200 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname hackerzork \
  --cores 1 \
  --memory 512 \
  --swap 512 \
  --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --start 1
```

## Step-by-Step: Provision the Container

Run `scripts/provision_lxc.sh` from inside the LXC (or paste manually):

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── System packages ────────────────────────────────────────────────────
apt update && apt upgrade -y
apt install -y \
  git python3.12 python3.12-venv python3-pip \
  nginx curl wget htop \
  build-essential libssl-dev  # needed for some Python deps

# ── SSH key auth for Patrick ───────────────────────────────────────────
mkdir -p /root/.ssh
chmod 700 /root/.ssh
# Paste Patrick's public key here:
echo "ssh-ed25519 AAAA... patrick@machine" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
# Disable password SSH login
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# ── Deployment directory ───────────────────────────────────────────────
mkdir -p /opt/hackerzork
useradd -r -s /usr/sbin/nologin -d /opt/hackerzork hackerzork
chown hackerzork:hackerzork /opt/hackerzork

# ── Clone repo ─────────────────────────────────────────────────────────
sudo -u hackerzork git clone \
  https://github.com/tricheboars/Hack3r-Z0rk \
  /opt/hackerzork/repo

# ── Python venv + dependencies ─────────────────────────────────────────
cd /opt/hackerzork/repo
sudo -u hackerzork python3.12 -m venv .venv
sudo -u hackerzork .venv/bin/pip install --upgrade pip
sudo -u hackerzork .venv/bin/pip install -r requirements.txt
sudo -u hackerzork .venv/bin/pip install -r browser-deploy/server/requirements.txt

# ── nginx ──────────────────────────────────────────────────────────────
cp /opt/hackerzork/repo/browser-deploy/nginx/hackerzork.conf \
   /etc/nginx/sites-available/hackerzork
ln -sf /etc/nginx/sites-available/hackerzork \
       /etc/nginx/sites-enabled/hackerzork
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx

# ── systemd service ────────────────────────────────────────────────────
cp /opt/hackerzork/repo/browser-deploy/systemd/hackerzork-ws.service \
   /etc/systemd/system/hackerzork-ws.service
systemctl daemon-reload
systemctl enable --now hackerzork-ws

echo "─────────────────────────────────────────────"
echo "  H@ck3r-Z0rk provisioned."
echo "  WebSocket server: systemctl status hackerzork-ws"
echo "  nginx: systemctl status nginx"
echo "─────────────────────────────────────────────"
```

## systemd Unit (`systemd/hackerzork-ws.service`)

```ini
[Unit]
Description=H@ck3r-Z0rk WebSocket Game Server
After=network.target

[Service]
Type=simple
User=hackerzork
WorkingDirectory=/opt/hackerzork/repo
ExecStart=/opt/hackerzork/repo/.venv/bin/python -m browser_deploy.server.ws_server
Restart=on-failure
RestartSec=5

# Environment
Environment=HZ_HOST=127.0.0.1
Environment=HZ_PORT=8765
Environment=HZ_MAX_SESSIONS=20
Environment=HZ_SESSION_TIMEOUT=1800
Environment=HZ_DEBUG=0

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/hackerzork/repo

[Install]
WantedBy=multi-user.target
```

## Deploy Script (`scripts/deploy.sh`)

```bash
#!/usr/bin/env bash
# Run on the LXC to pull latest code and restart the server
set -euo pipefail

cd /opt/hackerzork/repo
sudo -u hackerzork git pull origin main
sudo -u hackerzork .venv/bin/pip install -r requirements.txt -q
sudo -u hackerzork .venv/bin/pip install -r browser-deploy/server/requirements.txt -q
systemctl restart hackerzork-ws
echo "Deployed. Server restarting..."
systemctl status hackerzork-ws --no-pager
```

## Verification

After provisioning:

```bash
# Check server is running
systemctl status hackerzork-ws

# Test WebSocket locally
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: " \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8765/

# Check nginx is serving frontend
curl -s http://localhost/ | head -5

# Check from your Mac (replace IP)
open http://192.168.x.x/
```
