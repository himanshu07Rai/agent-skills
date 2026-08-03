---
name: nginx-certbot
description: "Install, configure, diagnose, and renew nginx + Let's Encrypt (certbot) on Ubuntu/Debian-style hosts — reverse proxies, static sites, SSL, renewals. Discover vhosts live."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [nginx, certbot, letsencrypt, ssl, reverse-proxy, https, vps]
    related_skills: [tailscale-logs, systematic-debugging, vps-health, docker-compose]
---

# Nginx + Certbot

Operate nginx and Let's Encrypt: status, vhosts, reverse proxies, cert issue/renew, logs, safe reloads. **Discover** layout and sites live — do not assume domain names, upstream ports, or a fixed site list.

## When to use

- Add/enable/disable a site or reverse proxy
- Issue or renew TLS certificates
- nginx errors, 502/504, SSL problems, redirect loops
- Expose a local app via HTTPS

## Discover first

```bash
command -v nginx; nginx -v 2>&1
command -v certbot; certbot --version 2>&1
systemctl is-active nginx 2>/dev/null
sudo nginx -t 2>&1

# Debian/Ubuntu layout (common)
ls -la /etc/nginx/sites-enabled/ 2>/dev/null
ls -la /etc/nginx/sites-available/ 2>/dev/null
ls /etc/nginx/conf.d/ 2>/dev/null

# map server_name → upstream/root (live)
sudo rg -n 'server_name|proxy_pass|root |ssl_certificate |listen ' \
  /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | head -80

sudo certbot certificates 2>/dev/null | head -60
systemctl list-timers 'certbot*' --no-pager 2>/dev/null
ss -tlnp 2>/dev/null | rg ':(80|443)\\s' || sudo ss -tlnp | rg ':(80|443)\\s'
```

Generic path reference (when distro uses it):

```text
Config:     /etc/nginx/nginx.conf
Vhosts:     /etc/nginx/sites-available/  (+ symlink enable)
Enabled:    /etc/nginx/sites-enabled/
Alt:        /etc/nginx/conf.d/*.conf
LE live:    /etc/letsencrypt/live/<domain>/
LE renewal: /etc/letsencrypt/renewal/
Web root:   /var/www/
Logs:       /var/log/nginx/
```

## Safety

1. Always `sudo nginx -t` before reload/restart.
2. Prefer `systemctl reload nginx` after a good test.
3. Do not casually hand-edit `# managed by Certbot` blocks — use certbot to change certs.
4. Backup a vhost before editing: `cp -a file file.bak.TIMESTAMP`.
5. Never paste private keys (`privkey.pem`) into chat.
6. Confirm DNS points at this host before issuing certificates.
7. Confirm upstream is listening before blaming nginx for 502.

---

## Workflow A — Status report

```bash
date -u
systemctl is-active nginx
sudo nginx -t
ls -la /etc/nginx/sites-enabled/ 2>/dev/null
sudo rg -n 'server_name|proxy_pass|root |listen ' /etc/nginx/sites-enabled/ 2>/dev/null
sudo certbot certificates 2>/dev/null
systemctl list-timers 'certbot*' --no-pager 2>/dev/null
sudo tail -n 40 /var/log/nginx/error.log 2>/dev/null
sudo journalctl -u nginx -u certbot.service --since '7 days ago' --no-pager 2>&1 \
  | rg -i 'error|warn|emerg|fail|renew|success' | tail -40
```

Optional HTTPS probes — only for domains the user names or that appear in live config:

```bash
for h in DOMAIN1 DOMAIN2; do
  curl -sS -o /dev/null -w "$h %{http_code} ssl_verify=%{ssl_verify_result}\n" \
    --connect-timeout 5 "https://$h/" || echo "$h failed"
done
```

### Report shape

```text
================================================================
NGINX OVERVIEW
================================================================
active | version | nginx -t | :80/:443 listen | time UTC

================================================================
SITES (from live config)
================================================================
file | server_name | listen | upstream/root | cert

================================================================
CERTIFICATES
================================================================
domain | expiry | issues | timer

================================================================
ERRORS
================================================================
```

---

## Workflow B — Reverse proxy + TLS

Variables from user/DNS discovery: `NAME`, `DOMAIN`, `PORT`, `EMAIL`.

### 1. Preconditions

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:PORT/" || true
ss -tlnp | rg ":PORT\\b" || true
dig +short A DOMAIN
curl -4 -s --max-time 3 ifconfig.me; echo
```

Stop if DNS does not target this host (unless user is doing DNS-01 intentionally).

### 2. HTTP vhost first

`/etc/nginx/sites-available/NAME`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:PORT;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

```bash
sudo ln -sfn /etc/nginx/sites-available/NAME /etc/nginx/sites-enabled/NAME
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Certbot nginx plugin

```bash
sudo certbot --nginx -d DOMAIN --agree-tos -m EMAIL --redirect --non-interactive
```

Agent/cron sessions need non-interactive + email; interactive OK if user is present.

### 4. Verify

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -sS -o /dev/null -w '%{http_code} %{url_effective}\n' -L "http://DOMAIN/"
curl -sS -o /dev/null -w '%{http_code}\n' "https://DOMAIN/"
```

---

## Workflow C — Static site + TLS

```bash
sudo mkdir -p /var/www/NAME
sudo chown -R www-data:www-data /var/www/NAME   # or appropriate user
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN;
    root /var/www/NAME;
    index index.html;
    location / {
        try_files $uri $uri/ =404;
    }
}
```

Then enable → test → reload → `certbot --nginx` as above.

---

## Workflow D — Useful location snippets

### WebSocket

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:BACKEND;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400s;
}
```

### SSE / streaming

```nginx
location /stream {
    proxy_pass http://127.0.0.1:PORT;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 1h;
    proxy_send_timeout 1h;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    chunked_transfer_encoding on;
}
```

### Path prefix

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:PORT/api/;  # trailing path rewrites — intentional
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Private IP only (e.g. VPN)

```nginx
server {
    listen PRIVATE_IP:443 ssl;
    server_name DOMAIN_OR_IP;
    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:PORT;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Discover private IPs live (`ip -br a`, `tailscale ip -4`); do not hardcode.

---

## Workflow E — Edit / disable / remove

```bash
sudo cp -a /etc/nginx/sites-available/NAME{,.bak.$(date +%Y%m%d%H%M%S)}
# edit carefully around certbot-managed lines
sudo nginx -t && sudo systemctl reload nginx
```

Disable: remove symlink from `sites-enabled`, test, reload.  
Delete cert only with user OK: `sudo certbot delete --cert-name DOMAIN`.

---

## Workflow F — Renewals

```bash
systemctl status certbot.timer --no-pager 2>/dev/null
sudo certbot renew --dry-run
sudo certbot certificates
# rare force:
# sudo certbot renew --cert-name DOMAIN --force-renewal
```

Renew fail checklist: DNS, :80 reachability, firewall, another process on :80, rate limits.

---

## Workflow G — Diagnose

| Symptom | Checks | Direction |
|---------|--------|-----------|
| 502 | upstream listen / curl localhost | start app; fix proxy_pass |
| 504 | timeouts / slow upstream | raise proxy_*_timeout; fix app |
| 404 | server_name / not enabled | enable site; fix name |
| challenge fail | DNS, :80, vhost | fix DNS/FW/HTTP server |
| redirect loop | app HTTPS + missing X-Forwarded-Proto | pass proto; trust proxy |
| expired cert | timer / renew logs | renew; fix timer |

```bash
sudo tail -n 100 /var/log/nginx/error.log
sudo nginx -T 2>/dev/null | rg -n "server_name DOMAIN|proxy_pass|ssl_certificate" | head -40
```

---

## Install (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo systemctl enable --now nginx
sudo systemctl enable --now certbot.timer
# if ufw:
# sudo ufw allow 'Nginx Full'
```

## What NOT to do

- Hardcode a permanent list of this machine's domains/upstreams into the skill
- reload without `nginx -t`
- delete certs/vhosts without confirmation
- issue certs without DNS proof
- dump private keys

## Verification

1. `nginx -t` OK  
2. nginx active  
3. HTTP→HTTPS and HTTPS status as expected for touched domains  
4. cert validity reported  
5. list files changed + backup paths  

## Related

- `vps-health` — host resources  
- `docker-compose` / `docker-stack` — app upstreams  
- `tailscale-logs` — private-only sites  
