# H@ck3r-Z0rk — LXC Container Operations

The game server runs in a Proxmox LXC container in the DMZ. This document
covers how it was provisioned, how to manage it day-to-day, and how to
diagnose problems.

---

## Network placement

| What | Value |
|------|-------|
| Container ID | 200 |
| Proxmox node | proxmox2 (10.1.30.11) |
| VLAN | 40 (DMZ) |
| IP | **10.1.40.101** (DHCP reservation) |
| MAC | BC:24:11:A6:32:78 |
| Hostname | `hackerzork` / `hackerzork.moorelab.internal` |
| SSH | `ssh hackerzork` (see `~/.ssh/config`) |

DNS is set on all four servers:
- OPNsense dnsmasq: `/usr/local/etc/dnsmasq.conf.d/lab-hosts.conf`
- Pi-hole ×2: `/etc/pihole/custom.list`

Firewall rules allow TCP 80 inbound from LAN (10.1.1.0/24) and Lab VLAN
(10.1.30.0/24). The container is not directly internet-facing.

---

## How the stack works

```
Browser  ──HTTP──▶  nginx :80  ──serves──▶  /opt/hackerzork/repo/website/game.html
                    nginx :80  ──proxy──▶   ws_server :8765 (loopback)
                    ws_server  ──boots──▶   Game() per WebSocket connection
                    Game()     ──uses──▶    hackerzork engine (filesystem, network, heat…)
```

**One isolated game session per browser tab.** Each WebSocket connection gets
its own `Game` instance with its own virtual filesystem, heat level, and
SkyNet state. Sessions are garbage-collected on disconnect.

**Audio is disabled** server-side (`audio_enabled=False`) — pygame can't run
headless in an LXC. Browser-side audio can be added later via Web Audio API.

---

## Services

### hackerzork-ws (WebSocket game server)

```bash
systemctl status hackerzork-ws
systemctl restart hackerzork-ws
journalctl -u hackerzork-ws -f          # live logs
journalctl -u hackerzork-ws --since "1h ago"
```

Configuration via environment variables in
`/etc/systemd/system/hackerzork-ws.service`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HZ_HOST` | `127.0.0.1` | Bind address (loopback — nginx proxies to it) |
| `HZ_PORT` | `8765` | WebSocket port |
| `HZ_MAX_SESSIONS` | `20` | Hard cap on concurrent sessions |
| `HZ_SESSION_TIMEOUT` | `1800` | Idle session kill (seconds, 30 min) |
| `HZ_DEBUG` | `0` | Set to `1` for verbose per-message logging |

To change a value: edit the `[Service]` `Environment=` lines in the unit file,
then `systemctl daemon-reload && systemctl restart hackerzork-ws`.

### nginx

```bash
systemctl status nginx
nginx -t                                # test config before reload
systemctl reload nginx                  # zero-downtime config reload
```

Config: `/etc/nginx/sites-available/hackerzork`
Serves: `/opt/hackerzork/repo/website/` (game.html, assets)
Proxies: `/ws` → `ws://127.0.0.1:8765`

---

## Deployment

### Normal update (code change)

```bash
ssh hackerzork
cd /opt/hackerzork/repo
sudo -u hackerzork git pull origin main
sudo -u hackerzork .venv/bin/pip install -e . -q
systemctl restart hackerzork-ws
```

Or use the deploy script:
```bash
ssh hackerzork 'bash /opt/hackerzork/repo/browser-deploy/scripts/deploy.sh'
```

### After adding a Python dependency

```bash
ssh hackerzork
sudo -u hackerzork /opt/hackerzork/repo/.venv/bin/pip install <package>
# Also add it to pyproject.toml or browser-deploy/server/requirements.txt
systemctl restart hackerzork-ws
```

### After changing the systemd unit

```bash
ssh hackerzork
# Edit /etc/systemd/system/hackerzork-ws.service
systemctl daemon-reload
systemctl restart hackerzork-ws
```

---

## Terraform

The container is managed by Terraform in `terraform/`. You should rarely need
to run it after initial provisioning — use `ssh hackerzork` + systemctl for
day-to-day ops.

```bash
cd terraform/
terraform plan   # preview changes
terraform apply  # apply (prompts for confirmation)
```

Secrets live in `terraform/terraform.tfvars` (gitignored):
```
proxmox_token_id     = "root@pam!homelab"
proxmox_token_secret = "…"
lxc_root_password    = "…"
```

The provider connects directly to the proxmox2 API (`https://10.1.30.11:8006/`)
because the cluster proxy on proxmox1 has a routing issue with cross-node
`POST /lxc` calls.

---

## Diagnostics

### Check if the WebSocket server is actually accepting connections

From the LXC itself:
```bash
/opt/hackerzork/repo/.venv/bin/python -c "
import asyncio, json, websockets
async def t():
    async with websockets.connect('ws://127.0.0.1:8765') as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=15)
        print('prompt len:', len(msg), '  ANSI:', repr(msg[:20]))
asyncio.run(t())
"
```

### Check nginx is proxying /ws correctly

From a machine with curl that can reach 10.1.40.101:
```bash
curl -i http://10.1.40.101/
# Should return 200 with the game.html page

curl -i --http1.1 -H "Upgrade: websocket" -H "Connection: Upgrade" \
     -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
     -H "Sec-WebSocket-Version: 13" \
     http://10.1.40.101/ws
# Should return 101 Switching Protocols
```

### Session count

```bash
journalctl -u hackerzork-ws --since "1h ago" | grep "connected from" | wc -l
journalctl -u hackerzork-ws --since "1h ago" | grep "disconnected"
```

### Disk / memory

```bash
df -h /opt/hackerzork    # disk
free -h                  # memory (container has 512MB dedicated + 512MB swap)
```

---

## Re-provisioning from scratch

If the container is ever nuked:

1. `cd terraform/ && terraform apply` — recreates CTID 200
2. Wait for DHCP to assign the same IP (reservation is on OPNsense Kea)
3. `ssh proxmox2 'pct exec 200 -- bash -s' < browser-deploy/scripts/provision_lxc.sh`
4. Verify: `ssh hackerzork 'systemctl status hackerzork-ws nginx'`

The DHCP reservation, DNS entries, and firewall rules are already in place
on the OPNsense HA pair — they survive a container rebuild.

---

## Future: internet-facing access

When ready to expose publicly:

1. Add `hackerzork.moorelab.cloud` to the Cloudflare DDNS script
2. Create a HAProxy backend on OPNsense pointing at 10.1.40.101:80
3. Add a Let's Encrypt certificate via certbot on the container and
   uncomment the TLS block in `/etc/nginx/sites-available/hackerzork`
4. Update the ACME challenge location in the nginx config
