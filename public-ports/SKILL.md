---
name: public-ports
description: "Audit which services are reachable on the public internet vs localhost vs Tailscale. Discover live listeners, Docker publishes, and nginx vhosts; no baked-in inventory."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ports, firewall, exposure, docker, nginx, tailscale, audit, vps]
    related_skills: [docker-stack, nginx-certbot, ssh-hardening, tailscale-logs, vps-health]
---

# Public ports audit

Read-only inventory of what this Linux host exposes. Classify every listen as **public**, **localhost**, or **private overlay** (Tailscale / other VPN). Discover live. Do not bake in container names, ports, domains, compose paths, or Tailscale IPs.

## When to use

- "What is public on this VPS?"
- "List public ports / public services"
- After binding something to Tailscale or `127.0.0.1`
- Before opening a cloud firewall or enabling UFW

## Discover first

```bash
date -u
hostnamectl 2>/dev/null | rg 'Static hostname|Operating System' || hostname
PUBLIC_IP=$(curl -4 -s --max-time 3 ifconfig.me); echo "PUBLIC_IP=$PUBLIC_IP"
command -v docker; command -v nginx; command -v tailscale
sudo ss -tlnp
docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null
tailscale ip -4 2>/dev/null
tailscale ip -6 2>/dev/null
```

Optional:

```bash
sudo ufw status 2>/dev/null || true
sudo iptables -L INPUT -n 2>/dev/null | head -20
# nginx public names (if nginx exists)
sudo grep -h 'server_name' /etc/nginx/sites-enabled/* 2>/dev/null | sed 's/;.*//' | sort -u
```

## Classification

| Host bind | Class | Meaning |
|-----------|--------|---------|
| `0.0.0.0:PORT`, `*:PORT`, `[::]:PORT`, bare `*:PORT` | **PUBLIC** | All interfaces. On a public VPS this is the internet **unless** a cloud/UFW firewall drops it |
| `127.0.0.1`, `::1` | **LOCAL** | Only this machine (typical behind nginx) |
| `100.64.0.0/10` (Tailscale CGNAT) or `fd7a:115c:` | **TAILSCALE** | Overlay only |
| Other RFC1918 / link-local | **PRIVATE** | LAN / other VPN — say which |

Docker `PORTS` column uses the same rules: `0.0.0.0:3000->3000` is PUBLIC; `127.0.0.1:3000->3000` is LOCAL; `100.x:3000->3000` is TAILSCALE.

Systemd vs Docker does **not** change exposure. A binary on `*:8080` is as public as `-p 0.0.0.0:8080:8080`.

## Report shape

```text
================================================================
PUBLIC PORTS  [time UTC]  PUBLIC_IP=  UFW=
================================================================

PUBLIC (internet if firewall allows)
port | process/container | also via nginx? | note

NGINX PUBLIC NAMES (if nginx listens :80/:443)
server_name | upstream bind class

LOCALHOST ONLY
port | process

TAILSCALE / PRIVATE
addr:port | process

ALERTS
unauthenticated DBs, kube API, message buses, extra app ports that skip TLS
```

Keep tables short. Do not dump `ss` raw or `docker inspect` Env.

## Alerts (flag, do not change unless asked)

Treat as high-risk if **PUBLIC**:

- Datastores: Redis `6379`, Postgres `5432`, MySQL `3306`, Mongo `27017`
- Brokers: Kafka `9092`, AMQP `5672`
- K8s: `6443`, `16443`, `10250`, `10257`, `10259`, `25000`
- Admin UIs bound on `0.0.0.0` (Dockge, nginx-ui, dashboards)
- App ports that **duplicate** an nginx HTTPS vhost (`3000` while nginx already `proxy_pass`es `localhost:3000`)

Intended public is usually: `22` (SSH), `80`/`443` (nginx). Call out everything else.

## Nginx vs extra publish

If nginx `proxy_pass http://127.0.0.1:PORT` (or `localhost:PORT`) **and** Docker/systemd also publishes `0.0.0.0:PORT`:

- HTTPS name = intended public
- Bare `http://PUBLIC_IP:PORT` = extra hole (no TLS, skips nginx)

Recommend (ask before applying): republish `127.0.0.1:HOSTPORT:CONTAINERPORT` or bind the systemd process to `127.0.0.1`. **Do not** change Dockerfiles for this — publish map / listen host only.

## Firewall caveat

Host `ss` showing `0.0.0.0:PORT` ≠ "reachable from the user's laptop".

- **UFW inactive** + cloud firewall allowing only 22/80/443 → OS says public, internet may still timeout
- Curl **from the VPS to its own PUBLIC_IP:PORT** can succeed (local hairpin) while remote curl times out

If the user says `curl http://PUBLIC_IP:PORT` fails from home but `ss` shows `0.0.0.0`, check provider firewall (Hetzner Cloud Firewall, etc.) and whether they used `https://` on a plain-HTTP port.

Do not enable UFW or change cloud firewalls unless the user explicitly asks (this user confirms security extras separately).

## Safety

- Read-only by default
- Never print `.env`, `EnvironmentFile`, or `docker inspect` Env
- Never bake this host's inventory into the skill after a run
- Do not bind new admin UIs to `0.0.0.0`

## What NOT to do

- Assume last session's port list is still true
- Treat Tailscale `100.x` as public
- Claim a port is unreachable from the internet solely because local curl to PUBLIC_IP worked or failed
- Edit Dockerfiles to "make it localhost"

## Verification

After an audit (or after a bind change you were asked to apply):

1. `sudo ss -tlnp` class matches the table
2. Docker `PORTS` column matches
3. Intended HTTPS names still 200
4. Extra public app ports gone if that was the goal (`127.0.0.1` or closed)

## Related

- `docker-stack` — container health / compose recreate
- `nginx-certbot` — vhosts / TLS
- `ssh-hardening` — SSH and host firewall (ask before UFW)
- `tailscale-logs` — overlay reachability
- `vps-health` — broader host health
