# Spec 04 — nginx Configuration

## Purpose

nginx sits in front of the WebSocket server. It handles:
- Serving static frontend files (index.html, term.js)
- Reverse-proxying `/ws` to the Python WebSocket server on port 8765
- TLS termination (optional — start without, add cert later)

## File: `nginx/hackerzork.conf`

## Config (LAN / no TLS — start here)

```nginx
server {
    listen 80;
    server_name _;   # catch-all — replace with hostname when you have one

    # ── Static frontend files ─────────────────────────────────────
    root /opt/hackerzork/browser-deploy/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # ── WebSocket reverse proxy ───────────────────────────────────
    location /ws {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;

        # WebSocket upgrade headers — REQUIRED
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";

        # Pass real client IP to the game server for logging
        proxy_set_header   X-Real-IP  $remote_addr;
        proxy_set_header   Host       $host;

        # Timeouts — keep long for idle sessions
        proxy_read_timeout  1800s;   # 30 min (matches HZ_SESSION_TIMEOUT)
        proxy_send_timeout  1800s;
        proxy_connect_timeout 10s;
    }
}
```

## Installing on LXC

```bash
# Copy config
cp /opt/hackerzork/browser-deploy/nginx/hackerzork.conf \
   /etc/nginx/sites-available/hackerzork

# Enable site
ln -s /etc/nginx/sites-available/hackerzork \
      /etc/nginx/sites-enabled/hackerzork

# Disable default site
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t && systemctl reload nginx
```

## Adding TLS with Let's Encrypt (later — when you have a domain)

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
# certbot auto-patches the nginx config — review the result
```

After certbot, the nginx config will have a second server block on 443.
The WebSocket in `term.js` should use `wss://` when the page is served over
HTTPS — the auto-detect logic in `term.js` handles this automatically.

## Self-signed cert (LAN with HTTPS — no domain needed)

```bash
openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout /etc/ssl/private/hackerzork.key \
  -out    /etc/ssl/certs/hackerzork.crt \
  -subj   "/CN=hackerzork.local"
```

Then add to the nginx config:
```nginx
listen 443 ssl;
ssl_certificate     /etc/ssl/certs/hackerzork.crt;
ssl_certificate_key /etc/ssl/private/hackerzork.key;
```

Browsers will warn about the self-signed cert — click through or add to
trust store on devices that will use it.
