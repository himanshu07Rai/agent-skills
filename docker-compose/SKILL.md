---
name: docker-compose
description: "Create and operate Docker Compose stacks on Linux — discover project dirs, up/down/pull/logs, env files, private vs public port binds. No fixed stack inventory."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [docker-compose, compose, stacks, yaml, vps]
    related_skills: [docker-stack, nginx-certbot, vps-health]
---

# Docker Compose Ops

Author and operate Compose (v2+ plugin) projects. **Discover** project paths and services live; never assume a fixed list of stacks, ports, or app names.

## When to use

- Add/edit a compose project
- `up -d` / `down` / `pull` / `logs` / `ps`
- Recreate after YAML changes
- Choose localhost / private / public port publishes

## Discover layout first

```bash
command -v docker >/dev/null && docker compose version
# common roots — use what exists
for d in "$HOME/compose" "$HOME/docker" /opt/stacks /opt/docker /srv/compose /srv/docker; do
  [ -d "$d" ] && echo "ROOT=$d" && find "$d" -maxdepth 2 \( -name 'compose.y*ml' -o -name 'docker-compose.y*ml' \) 2>/dev/null
done
# from a running container
NAME=<container>
docker inspect -f 'workdir={{index .Config.Labels "com.docker.compose.project.working_dir"}}
config={{index .Config.Labels "com.docker.compose.project.config_files"}}
project={{index .Config.Labels "com.docker.compose.project"}}
service={{index .Config.Labels "com.docker.compose.service"}}' "$NAME" 2>/dev/null
```

Compose filenames to try (in order): `compose.yaml`, `compose.yml`, `docker-compose.yml`, `docker-compose.yaml`.

If a UI manager (e.g. Dockge) is present, discover via `docker ps` + its labels/mounts — do not hardcode URLs or stack lists.

## Safety

- Never paste `.env`, tokens, or passwords into chat.
- Backup compose files + know volume paths before `down -v`.
- `docker compose down -v` deletes volumes — explicit user OK only.
- Prefer loopback or private-overlay binds for admin UIs; public HTTPS via reverse proxy when needed.
- `docker compose config` before apply.

---

## Helper: resolve compose file in a directory

```bash
compose_file() {
  local d="${1:-.}"
  for f in compose.yaml compose.yml docker-compose.yml docker-compose.yaml; do
    [ -f "$d/$f" ] && { echo "$d/$f"; return 0; }
  done
  return 1
}
```

---

## Workflow A — Project status

```bash
DIR=<project_dir>    # discovered or user-provided
cf=$(compose_file "$DIR") || { echo 'no compose file'; exit 1; }
docker compose -f "$cf" ps
docker compose -f "$cf" images
```

---

## Workflow B — Logs / pull / recreate

```bash
DIR=<project_dir>
cf=$(compose_file "$DIR")
docker compose -f "$cf" logs --tail 100
docker compose -f "$cf" pull
docker compose -f "$cf" up -d
docker compose -f "$cf" ps
docker compose -f "$cf" logs --tail 40
```

Single service: `docker compose -f "$cf" up -d SERVICE` (SERVICE from compose file / `ps`, not guessed).

---

## Workflow C — Create a new stack

```bash
DIR=<parent>/<stack_name>
mkdir -p "$DIR/data"
umask 077
touch "$DIR/.env" && chmod 600 "$DIR/.env"
```

Templates (replace IMAGE, ports, paths):

**Private / admin (loopback — nginx or tunnel in front):**

```yaml
services:
  app:
    image: IMAGE
    restart: unless-stopped
    ports:
      - "127.0.0.1:HOSTPORT:CONTAINERPORT"
    env_file: .env
    volumes:
      - ./data:/data
```

**Private overlay (e.g. Tailscale IP on host — discover IP live):**

```bash
# example discovery only if tailscale present
TS_IP=$(tailscale ip -4 2>/dev/null || true)
```

```yaml
services:
  app:
    image: IMAGE
    restart: unless-stopped
    ports:
      - "TS_IP:HOSTPORT:CONTAINERPORT"   # only if TS_IP known
    env_file: .env
    volumes:
      - ./data:/data
```

**Intentionally public (prefer still terminating TLS at proxy):**

```yaml
ports:
  - "0.0.0.0:HOSTPORT:CONTAINERPORT"
```

```bash
cf="$DIR/compose.yaml"
docker compose -f "$cf" config
docker compose -f "$cf" up -d
docker compose -f "$cf" ps
```

Public apps needing HTTPS → skill `nginx-certbot` with `proxy_pass` to the chosen host port.

---

## Workflow D — Edit existing project

```bash
DIR=<project_dir>
cf=$(compose_file "$DIR")
cp -a "$cf" "${cf}.bak.$(date +%Y%m%d%H%M%S)"
# edit image/ports/volumes
docker compose -f "$cf" config
docker compose -f "$cf" up -d
```

Changing volume paths does not migrate data — move files deliberately.

---

## Workflow E — Stop / remove

```bash
cf=$(compose_file "$DIR")
docker compose -f "$cf" down          # keep volumes
# explicit OK only:
# docker compose -f "$cf" down -v
```

---

## Workflow F — Conventions (generic)

1. One directory per stack; compose file at project root.
2. Prefer `compose.yaml` for new projects.
3. `restart: unless-stopped` for long-running services.
4. Secrets in `.env` mode `600`, referenced as `${VAR}`.
5. Admin UIs: not on `0.0.0.0` unless user explicitly wants that.
6. Healthchecks when the image supports them.
7. If both a GUI stack manager and CLI are used, operate on the **same** project directory to avoid split brain.

---

## What NOT to do

- Do not embed a host-specific inventory of stacks/ports in reports as if permanent
- Do not `down -v` on stateful apps without backup + OK
- Do not print compose files that contain live secrets; redact
- Do not assume `/opt/stacks` vs `$HOME/compose` — discover mounts/labels

## Verification

1. `docker compose config` OK  
2. `ps` shows running/(healthy)  
3. Port bind matches intent  
4. Logs clean of crash loops  
5. If proxied: frontend URL check  

## Related

- `docker-stack` — engine-wide inventory and prune  
- `nginx-certbot` — public TLS  
- `vps-health` — resources before large pulls  
