---
name: docker-stack
description: "Manage Docker on a Linux host — inventory, logs, restart, updates, prune-with-approval, and public vs private port-bind audit. Discover running state live; never assume a fixed container list."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [docker, containers, vps, stacks, prune, logs, networking]
    related_skills: [docker-compose, vps-health, nginx-certbot, tailscale-logs]
---

# Docker Stack Ops

Day-2 Docker engine operations: inventory, health, logs, restart/update, disk reclaim, and bind-address awareness. Discover everything live. For Compose file workflows see skill `docker-compose`.

## When to use

- Container status, unhealthy, restart loops
- Logs / update image / stop-start a named service
- Disk pressure from Docker (`docker system df`)
- "Is this port public or private?"
- After a host health check flags Docker RAM/disk issues

## Discover first (always)

Do **not** use a baked-in list of container names, images, or ports. Run:

```bash
command -v docker >/dev/null || { echo 'docker not installed'; exit 0; }
docker info 2>/dev/null | rg -i 'Server Version|Containers:|Running:|Paused:|Stopped:|Images:|Docker Root Dir|Storage Driver|ERROR|Name:'
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker compose version 2>/dev/null || true
```

Optional: locate common compose roots without assuming one path:

```bash
for d in "$HOME/compose" /opt/stacks /srv/docker /opt/docker; do
  [ -d "$d" ] && echo "compose_root_candidate=$d"
done
```

## Safety

- Read-only by default for audits.
- **Never** `docker system prune -a --volumes` without explicit user approval (data loss).
- Do not print `.env`, tokens, DB passwords, or `docker inspect` Env blocks.
- Prefer restarting a single container over mass restart.
- Confirm intent before publishing new ports on `0.0.0.0`.
- Updating `:latest` can break apps — note prior image id/digest when possible.

---

## Workflow A — Inventory / health report

```bash
date -u
docker info 2>/dev/null | rg -i 'Server Version|Containers:|Running:|Paused:|Stopped:|Images:|Docker Root Dir|Storage Driver|ERROR'
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker ps -a --filter health=unhealthy --format '{{.Names}} {{.Status}}'
docker ps -a --filter status=exited --format '{{.Names}} {{.Status}}'
docker system df
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' 2>/dev/null | head -25
```

### Report shape

```text
================================================================
DOCKER OVERVIEW
================================================================
engine version | running/stopped/unhealthy counts | disk df | time UTC

================================================================
CONTAINERS
================================================================
name | image | status | ports (classify bind) | notes

================================================================
DISK
================================================================
images / containers / volumes sizes + reclaimable (do not prune yet)

================================================================
ALERTS
================================================================
unhealthy, unexpected exited, large reclaimable, surprising public binds
```

---

## Workflow B — Logs & diagnose one container

```bash
NAME=<container>   # from user or docker ps — never invent
docker ps -a --filter name=^/${NAME}$ --format '{{.Names}} {{.Status}} {{.Ports}}'
docker logs --tail 100 "$NAME" 2>&1
docker inspect -f 'RestartCount={{.RestartCount}} OOM={{.State.OOMKilled}} Exit={{.State.ExitCode}} Error={{.State.Error}} Started={{.State.StartedAt}}' "$NAME"
docker inspect -f 'Binds={{json .HostConfig.Binds}} Ports={{json .HostConfig.PortBindings}}' "$NAME" | head -c 2000; echo
```

If nginx fronts the app, check upstream separately (skill `nginx-certbot`). Local probe:

```bash
# PORT from docker ps publish map
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 3 "http://127.0.0.1:PORT/" || true
```

---

## Workflow C — Restart / stop / start

```bash
NAME=<container>
docker restart "$NAME"
docker ps --filter name=^/${NAME}$ --format '{{.Names}} {{.Status}}'
docker logs --tail 30 "$NAME" 2>&1
```

- Stop without delete: `docker stop NAME`
- Start existing: `docker start NAME`
- Do not `docker rm -v` unless user confirms volume disposal

If the container has Compose labels, prefer compose recreate (skill `docker-compose`).

---

## Workflow D — Update image

```bash
NAME=<container>
IMG=$(docker inspect -f '{{.Config.Image}}' "$NAME")
docker inspect -f 'project={{index .Config.Labels "com.docker.compose.project"}}
workdir={{index .Config.Labels "com.docker.compose.project.working_dir"}}
config={{index .Config.Labels "com.docker.compose.project.config_files"}}' "$NAME"
```

If compose labels present → `docker compose -f ... pull && up -d` from workdir.  
If standalone → `docker pull "$IMG"` then recreate only with a known run method (compose preferred). Do not guess full `docker run` flags from memory.

---

## Workflow E — Disk reclaim (approval required)

```bash
docker system df -v 2>/dev/null | head -80
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' | head -40
```

Ask before each escalating step:

```bash
docker image prune -f                 # dangling only — still confirm if unsure
# explicit OK:
docker image prune -a
docker container prune
docker network prune
# NEVER default:
# docker system prune -a --volumes
```

Report reclaimable sizes first; prune second.

---

## Workflow F — Bind exposure audit

```bash
docker ps --format '{{.Names}}\t{{.Ports}}'
```

Classify each publish:

| Host bind pattern | Meaning |
|-------------------|---------|
| `127.0.0.1:PORT` | localhost only (good behind reverse proxy) |
| `100.x.x.x:PORT` or tailnet IP | typically Tailscale/private overlay only |
| `0.0.0.0:PORT` / `[::]:PORT` / bare `PORT` | all interfaces — public if host is public |
| no host port | internal docker network only |

Optional: compare with `ss -tlnp` for listeners. Flag unexpected public admin UIs or databases.

---

## What NOT to do

- Do not hardcode or reuse a previous session's container inventory as truth
- Do not cat env files or print secrets from inspect
- Do not prune volumes without explicit OK
- Do not bind new admin UIs to `0.0.0.0` by default
- Do not mount `docker.sock` into untrusted images without warning

## Verification

1. `docker ps` shows expected status (healthy if healthcheck exists)  
2. Recent logs show no crash loop  
3. Local/port checks match intent  
4. If proxied, HTTPS/frontend check still works  

## Related

- `docker-compose` — project files, up/down/pull  
- `vps-health` — host RAM/disk context  
- `nginx-certbot` — reverse proxy / TLS  
- `tailscale-logs` — private-network reachability  
