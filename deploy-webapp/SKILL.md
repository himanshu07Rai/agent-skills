---
name: deploy-webapp
description: "End-to-end deploy a web app on a Linux VPS — choose runtime (compose/docker/static/systemd), bind locally, nginx reverse proxy, Let's Encrypt, health checks, and rollback. Discover paths live; no fixed app inventory."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [deploy, webapp, nginx, docker, compose, certbot, tls, vps, release]
    related_skills: [docker-compose, docker-stack, nginx-certbot, vps-health, postgres-redis-ops, ssh-hardening]
---

# Deploy Webapp (end-to-end)

Ship a web application on a Linux host from “code/image ready” to “HTTPS works”, with verification and a simple rollback path.

This skill **orchestrates** specialized skills:
- App runtime → `docker-compose` / `docker-stack` / systemd / static files
- Edge TLS → `nginx-certbot`
- Host capacity → `vps-health` (quick check if resources are tight)
- DB if needed → `postgres-redis-ops`

**Never** hardcode domains, ports, container names, or project paths. Take them from the user or discover live.

## When to use

- “Deploy my app at `app.example.com`”
- First-time expose of a local service via HTTPS
- Redeploy / update an already-proxied app
- “Wire docker + nginx + certbot for me”

## Inputs to collect (ask only if missing)

| Input | Required | Notes |
|-------|----------|--------|
| `DOMAIN` | yes (public HTTPS) | FQDN user controls |
| `EMAIL` | yes for new LE cert | Let's Encrypt contact |
| Runtime | yes | compose \| docker image \| static \| systemd binary |
| `PROJECT_DIR` or image | yes | where compose/files live, or image ref |
| `HOSTPORT` | yes | port nginx will `proxy_pass` to (prefer `127.0.0.1`) |
| `CONTAINERPORT` | if container | internal listen port |
| Path prefix | no | default `/` |
| Needs websocket/SSE | no | longer proxy timeouts |
| Needs DB | no | create/migrate separately |
| Public vs private | yes | internet HTTPS vs VPN/Tailscale-only |

If private-only: skip public DNS/LE; bind private IP or Tailscale IP and stop after app health (or TLS with private certs if user wants).

---

## Safety

1. Quick resource glance before large image pulls (`free -h`, `df -h /`) — full audit only if tight.
2. Prefer app bind **`127.0.0.1:HOSTPORT`** (or private IP). Avoid `0.0.0.0` unless user explicitly wants direct public expose without nginx.
3. Backup existing nginx vhost / compose file before overwrite.
4. `nginx -t` before every reload.
5. Never print `.env`, API keys, DB passwords, or private keys.
6. DNS must point to this host before HTTP-01 certbot (unless user chooses DNS-01).
7. Do not delete old containers/volumes without OK.
8. One change layer at a time: app up → local curl OK → nginx HTTP → cert → HTTPS verify.

---

## Phase 0 — Preflight (always)

```bash
date -u
whoami
# capacity snapshot
free -h | head -2
df -h / | tail -1
# tools
command -v docker; docker compose version 2>/dev/null
command -v nginx; command -v certbot
systemctl is-active nginx 2>/dev/null
# public IP vs DNS (public deploys)
curl -4 -s --max-time 3 ifconfig.me; echo
dig +short A "$DOMAIN" 2>/dev/null
dig +short AAAA "$DOMAIN" 2>/dev/null
```

Gate:

| Check | Fail action |
|-------|-------------|
| Disk > ~90% or &lt;2G free | stop; suggest cleanup before pull |
| DNS A/AAAA ≠ this host (public) | stop; user fixes DNS |
| nginx missing (public HTTPS path) | install via nginx-certbot skill or apt |
| Port HOSTPORT already taken by wrong app | pick another port or stop conflict |

Discover free port if user did not specify:

```bash
# example: find an unused high port
for p in 3000 3001 3080 4000 8080 8081; do
  ss -tln | rg -q ":$p\\s" || { echo "free_port=$p"; break; }
done
```

Discover compose roots if `PROJECT_DIR` unknown:

```bash
for d in "$HOME/compose" "$HOME/docker" /opt/stacks /opt/docker /srv/compose; do
  [ -d "$d" ] && find "$d" -maxdepth 2 \( -name 'compose.y*ml' -o -name 'docker-compose.y*ml' \) 2>/dev/null
done
```

---

## Phase 1 — Run the app

Pick **one** runtime path.

### Path A — Docker Compose (preferred when YAML exists or new stack)

Follow skill `docker-compose` conventions.

```bash
PROJECT_DIR=<dir>
mkdir -p "$PROJECT_DIR"
# write or update compose so published port is loopback:
#   ports: ["127.0.0.1:HOSTPORT:CONTAINERPORT"]
# env in .env mode 600 — do not echo secrets
cf=compose.yaml   # or discovered name
docker compose -f "$PROJECT_DIR/$cf" config
docker compose -f "$PROJECT_DIR/$cf" pull
docker compose -f "$PROJECT_DIR/$cf" up -d
docker compose -f "$PROJECT_DIR/$cf" ps
docker compose -f "$PROJECT_DIR/$cf" logs --tail 50
```

### Path B — Single container

```bash
docker pull IMAGE
docker rm -f APP_NAME 2>/dev/null || true
docker run -d --name APP_NAME --restart unless-stopped \
  -p 127.0.0.1:HOSTPORT:CONTAINERPORT \
  --env-file /path/to/.env \
  IMAGE
docker ps --filter name=^/APP_NAME$
docker logs --tail 50 APP_NAME
```

Only use this when no compose file; prefer migrating to compose for repeatability.

### Path C — Static files

```bash
WEB_ROOT=/var/www/NAME
sudo mkdir -p "$WEB_ROOT"
# rsync/copy build output into WEB_ROOT
sudo chown -R www-data:www-data "$WEB_ROOT"   # or appropriate user
```

Nginx serves `root` directly (nginx-certbot static workflow) — no `proxy_pass`.

### Path D — Systemd-managed binary/Node/etc.

```bash
# install binary or app under /opt/NAME or $HOME/apps/NAME
# unit listens on 127.0.0.1:HOSTPORT
sudo systemctl daemon-reload
sudo systemctl enable --now APP.service
systemctl is-active APP.service
journalctl -u APP.service -n 50 --no-pager
```

### Phase 1 gate — local health

```bash
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 5 "http://127.0.0.1:HOSTPORT/" || true
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 5 "http://127.0.0.1:HOSTPORT/health" || true
ss -tlnp | rg ":HOSTPORT\\b" || sudo ss -tlnp | rg ":HOSTPORT\\b"
```

**Do not continue to nginx until local HTTP succeeds** (or static files exist). If app needs DB, verify DB first (`postgres-redis-ops`) and run migrations here.

---

## Phase 2 — Nginx reverse proxy (HTTP)

Use skill `nginx-certbot` Workflow B patterns. Debian/Ubuntu:

```bash
NAME=<short_slug>          # e.g. app name, not full domain
DOMAIN=<fqdn>
HOSTPORT=<port>
```

Write `/etc/nginx/sites-available/$NAME` (backup first if exists):

```bash
if [ -f "/etc/nginx/sites-available/$NAME" ]; then
  sudo cp -a "/etc/nginx/sites-available/$NAME" \
    "/etc/nginx/sites-available/$NAME.bak.$(date +%Y%m%d%H%M%S)"
fi
```

Base proxy server (HTTP only first):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:HOSTPORT;
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

If websocket/SSE: keep upgrade headers + long timeouts (see nginx-certbot snippets).  
If static: use `root` + `try_files` instead of `proxy_pass`.

```bash
sudo ln -sfn "/etc/nginx/sites-available/$NAME" "/etc/nginx/sites-enabled/$NAME"
# remove default site only if it steals server_name and user OK
sudo nginx -t && sudo systemctl reload nginx
curl -sS -o /dev/null -w '%{http_code} %{url_effective}\n' -H "Host: $DOMAIN" "http://127.0.0.1/" || true
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 5 "http://$DOMAIN/" || true
```

Firewall: if ufw active, ensure 80/443 allowed (ssh-hardening / ufw notes). Do not lock SSH.

---

## Phase 3 — TLS (Let's Encrypt)

```bash
EMAIL=<email>
sudo certbot --nginx -d "$DOMAIN" --agree-tos -m "$EMAIL" --redirect --non-interactive
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certificates 2>/dev/null | rg -A4 "$DOMAIN" || sudo certbot certificates 2>/dev/null | head -40
```

If certbot fails: DNS, port 80 reachability, rate limits, broken vhost — fix then retry (nginx-certbot Workflow G). Do not force-renew casually.

---

## Phase 4 — Final verification

```bash
# HTTPS
curl -sS -o /dev/null -w 'https_code=%{http_code} ssl=%{ssl_verify_result} time=%{time_total}\n' \
  --connect-timeout 10 "https://$DOMAIN/"
# HTTP should redirect
curl -sS -o /dev/null -w 'http_code=%{http_code} redirect=%{redirect_url}\n' \
  --connect-timeout 5 -L --max-redirs 0 "http://$DOMAIN/" || true
# app still local
curl -sS -o /dev/null -w 'local=%{http_code}\n' "http://127.0.0.1:HOSTPORT/" || true
# process/container
docker ps --filter publish=HOSTPORT 2>/dev/null | head -5
systemctl is-active nginx
```

### Success report shape

```text
================================================================
DEPLOY OK | PARTIAL | FAILED
================================================================
Domain:      
Runtime:     compose|docker|static|systemd
Project/dir: 
Upstream:    127.0.0.1:HOSTPORT
Nginx site:  /etc/nginx/sites-available/NAME
TLS:         certbot|skipped|failed
Checks:      local=  http=  https=
Backups:     list .bak paths if any
Rollback:    how to undo (below)
================================================================
```

---

## Redeploy / update (existing site)

1. Discover current upstream from nginx config:

```bash
sudo rg -n "server_name $DOMAIN|proxy_pass" /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null
```

2. Discover compose labels or project dir from container (docker-compose skill).  
3. `pull` + `up -d` (or rebuild).  
4. Local curl gate.  
5. Reload nginx only if vhost changed.  
6. HTTPS curl verify — cert usually unchanged.

Do not re-run certbot on every deploy unless cert/domain changed.

---

## Private / Tailscale-only deploy

When user does **not** want public internet:

1. Phase 1 with publish `127.0.0.1:HOSTPORT` or `TS_IP:HOSTPORT`  
   (`TS_IP=$(tailscale ip -4 2>/dev/null)`)  
2. Optional nginx on private IP only (nginx-certbot private listen snippet).  
3. Skip public DNS + certbot HTTP-01 (or use internal CA / self-signed if asked).  
4. Verify via private URL/IP; do not claim public HTTPS.

---

## Rollback

**App (compose):**

```bash
cd PROJECT_DIR
# previous image id if noted, or git checkout previous compose
docker compose -f FILE up -d
```

**App (container):** retag/run previous image id.

**Nginx:**

```bash
sudo cp -a /etc/nginx/sites-available/NAME.bak.TIMESTAMP /etc/nginx/sites-available/NAME
sudo nginx -t && sudo systemctl reload nginx
```

**Certbot:** rarely roll back; removing site symlink is enough to stop serving. Do not `certbot delete` unless user wants cert gone.

**Full disable:**

```bash
sudo rm -f /etc/nginx/sites-enabled/NAME
sudo nginx -t && sudo systemctl reload nginx
docker compose -f FILE stop   # or docker stop APP
```

---

## Failure matrix

| Stage | Symptom | What to do |
|-------|---------|------------|
| Preflight | DNS mismatch | fix DNS; wait TTL |
| App | container exit / OOM | logs; vps-health; more RAM/swap |
| App | local curl fail | logs; wrong PORT; app not listening 0.0.0.0 inside container |
| Nginx | 502 | upstream down; proxy_pass host/port; SELinux rare on Ubuntu |
| Nginx | 404 | wrong server_name; default site caught request |
| Certbot | challenge fail | :80 blocked; DNS; AAAA to wrong host |
| HTTPS | redirect loop | app forces HTTPS without trusting X-Forwarded-Proto |
| HTTPS | 526/wrong cert | leftover cert; SNI/server_name mismatch |

---

## What NOT to do

- Skip local health check and jump straight to certbot  
- Bind admin apps publicly “temporarily” without saying so  
- Embed this host’s existing site list into the skill or assume ports  
- Paste secrets from `.env` into chat or nginx configs  
- `docker compose down -v` as part of normal deploy  
- Reboot the VPS as a deploy step  

## Verification checklist

1. App healthy on `127.0.0.1:HOSTPORT` (or static root populated)  
2. `nginx -t` OK, site enabled  
3. `https://DOMAIN` returns expected status  
4. HTTP→HTTPS redirect if certbot --redirect  
5. User given paths changed + rollback commands  

## Related skills

- `docker-compose` / `docker-stack` — runtime details  
- `nginx-certbot` — vhost/TLS deep dive  
- `vps-health` — resource pressure  
- `postgres-redis-ops` — DB provision/migrate  
- `ssh-hardening` — only if deploy includes firewall exposure decisions  
