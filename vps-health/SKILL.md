---
name: vps-health
description: "Check overall VPS health on this Ubuntu host — CPU, RAM, disk, load, failed services, reboot-needed, Docker/MicroK8s, nginx, DB, network, and top resource hogs. Produce a concise traffic-light report."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vps, health, monitoring, disk, memory, cpu, docker, systemd, ubuntu, hetzner, diagnostics]
    related_skills: [nginx-certbot, tailscale-logs, systematic-debugging, homepage-dashboard]
---

# VPS Health Check (this host)

Fast, structured health audit of the local Ubuntu VPS. Prefer **summary + alerts** over raw dumps. Deep-dive nginx/Tailscale only when those are the issue (use related skills).

## When to use

- User asks: "is the server OK?", "VPS health", "why is it slow?", "disk/RAM/CPU check"
- After deploys, crashes, OOM suspicion, or before/after reboot
- Periodic sanity check / cron-style briefing
- "What's eating resources?"

## Host profile (re-discover each run; snapshot at authoring)

```text
Provider/region:  Hetzner (hostname pattern *-nbg1-*)
OS:               Ubuntu 24.04 LTS (noble), systemd
Size class:       ~8GB RAM / 4 vCPU / ~75G root (verify live)
Hostname ex:      ubuntu-8gb-nbg1-1
Swap:             often none — memory pressure is critical
Notable stacks:   nginx, Docker, MicroK8s (calico), PostgreSQL 16,
                  Redis, Tailscale, certbot.timer, unattended-upgrades,
                  qemu-guest-agent, api.service, nginx-ui
Public IF:        eth0 (public v4/v6)
Tailnet IF:       tailscale0 (100.x)
```

Do **not** hardcode free RAM/disk % from this skill text — always measure live.

## Safety / etiquette

- Read-only by default. Do not restart services, reboot, or free disk unless the user asks.
- Do not dump full `docker inspect`, full `ps aux`, or multi-MB logs.
- Do not print secrets from env files or container configs.
- If sudo is needed and fails, report what could not be checked.
- Cap process lists (top 8–10). Cap journal lines (~40–80 high-signal).

## Thresholds (traffic lights)

Use these defaults unless user overrides:

| Metric | OK | WARN | CRIT |
|--------|----|------|------|
| Root disk use% | < 75% | 75–90% | ≥ 90% or Avail < 2G |
| Inode use% | < 80% | 80–95% | ≥ 95% |
| Memory available | > 15% of total | 10–15% | < 10% or < 300Mi |
| Swap used (if any) | < 50% | 50–80% | ≥ 80% or thrashing |
| Load average (1m) | < nproc | nproc–2×nproc | > 2×nproc sustained |
| Failed systemd units | 0 | — | ≥ 1 |
| `/var/run/reboot-required` | absent | present | present + security kernels stacked |
| Docker unhealthy / exited (unexpected) | 0 | 1–2 | many / restart loops |
| nginx -t | ok | — | fail |
| Clock sync | synchronized | — | unsynchronized |

"Available" memory = `free -h` **available** column (includes reclaimable cache), not just "free".

---

## Workflow (run in order, one pass)

Collect with a tight shell batch where possible. Skip sections cleanly if a stack is absent.

### 1. Identity & uptime

```bash
date -u
hostnamectl 2>/dev/null || hostname
cat /etc/os-release | rg '^(NAME|VERSION|VERSION_ID)='
uname -r
uptime
who -b 2>/dev/null
timedatectl 2>/dev/null | rg 'Local time|Universal|Time zone|synchronized|NTP'
```

### 2. CPU & load

```bash
nproc
# load vs cores
uptime
# top CPU processes
ps aux --sort=-%cpu | head -n 11
# optional brief: vmstat 1 3  (if installed)
command -v vmstat >/dev/null && vmstat 1 3
```

Note steal time (`st` in vmstat) on cloud VMs — high steal = noisy neighbor / undersized plan.

### 3. Memory & swap (critical on no-swap hosts)

```bash
free -h
# top RSS processes
ps aux --sort=-%mem | head -n 11
# OOM kills recent?
sudo journalctl -k --since "7 days ago" --no-pager 2>&1 \
  | rg -i 'Out of memory|Killed process|oom-kill|Memory cgroup' | tail -30
# pressure (if available)
cat /proc/pressure/memory 2>/dev/null
swapon --show
```

If swap is empty/absent and available RAM is WARN/CRIT → call out **add swap or reduce workload** as primary recommendation.

### 4. Disk & inodes

```bash
df -hT
df -i
# largest dirs on root (fast depth, may need sudo)
sudo du -xh / --max-depth=2 2>/dev/null | sort -hr | head -n 25
# common growth points
sudo du -sh /var/lib/docker /var/log /var/lib/containerd /var/lib/rancher \
  /snap /home /tmp /var/cache/apt /var/lib/microk8s 2>/dev/null
# journal disk use
journalctl --disk-usage 2>/dev/null
```

Flag: docker images/build cache, old snaps, large journals, leftover logs.

### 5. Systemd health

```bash
systemctl is-system-running 2>/dev/null
systemctl --failed --no-pager
# key services on this host (ignore missing)
for u in nginx docker containerd postgresql redis-server tailscaled ssh \
         cron certbot.timer unattended-upgrades qemu-guest-agent api \
         nginx-ui snap.microk8s.daemon-kubelite; do
  state=$(systemctl is-active "$u" 2>/dev/null || echo missing)
  en=$(systemctl is-enabled "$u" 2>/dev/null || echo n/a)
  printf '%-40s %s (%s)\n' "$u" "$state" "$en"
done
```

### 6. Reboot / updates pending

```bash
ls -la /var/run/reboot-required 2>/dev/null
cat /var/run/reboot-required.pkgs 2>/dev/null | head -40
# running vs installed kernel
echo "running: $(uname -r)"
ls -1 /boot/vmlinuz-* 2>/dev/null | tail -5
# unattended upgrades status
systemctl is-active unattended-upgrades 2>/dev/null
sudo needrestart -b 2>/dev/null | head -40 || needrestart -b 2>/dev/null | head -40
```

If reboot-required: report **pending reboot** (do not reboot unless asked). Mention services needing restart from needrestart when available.

### 7. Network quick view

```bash
ip -br a
ip route | head -10
# listening sockets summary (public-facing especially)
sudo ss -tlnp | rg ':(22|80|443|3000|8000|8080|5432|6379)\s' || ss -tlnp | head -40
ss -s
# optional external IP
curl -4 -s --max-time 3 ifconfig.me; echo
curl -6 -s --max-time 3 ifconfig.me 2>/dev/null; echo
```

Do not full-scan ports. Note Docker publishes and Tailscale-bound services (often `100.x:port`).

### 8. Docker (if installed)

```bash
docker info 2>/dev/null | rg -i 'Server Version|Containers:|Running:|Paused:|Stopped:|Images:|MemTotal|ERROR'
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -40
# restarting / unhealthy
docker ps -a --filter health=unhealthy --format '{{.Names}} {{.Status}}' 2>/dev/null
docker ps -a --filter status=exited --format '{{.Names}} {{.Status}}' 2>/dev/null | head -20
docker system df 2>/dev/null
```

Summarize: running vs exited, unhealthy names, disk reclaimable.

### 9. MicroK8s / k8s (if present)

```bash
command -v microk8s >/dev/null && microk8s status 2>/dev/null | head -40
command -v microk8s >/dev/null && microk8s kubectl get nodes 2>/dev/null
command -v microk8s >/dev/null && microk8s kubectl get pods -A 2>/dev/null \
  | rg -v 'Running|Completed' | head -30
```

If microk8s missing/stopped, one line: skipped. Don't install it.

### 10. Data stores (if present)

```bash
systemctl is-active postgresql redis-server 2>/dev/null
# postgres quick
sudo -u postgres psql -c 'SELECT version();' 2>/dev/null | head -3
sudo -u postgres psql -c 'SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC;' 2>/dev/null | head -20
# redis
redis-cli ping 2>/dev/null
redis-cli info memory 2>/dev/null | rg 'used_memory_human|maxmemory_human'
```

Skip auth-heavy details; connectivity + size is enough.

### 11. Nginx + certs (lightweight — defer deep work)

```bash
systemctl is-active nginx
sudo nginx -t 2>&1
ls /etc/nginx/sites-enabled 2>/dev/null
# cert expiry only if certbot works
sudo certbot certificates 2>/dev/null | rg -i 'Certificate Name|Expiry Date|INVALID|ERROR' | head -40
```

For vhost edits/renew failures → hand off to skill `nginx-certbot`.

### 12. Tailscale one-liner (not full audit)

```bash
tailscale status 2>/dev/null | head -20
```

Full peer/log diagnosis → skill `tailscale-logs`.

### 13. Recent critical logs

```bash
sudo journalctl -p err..alert --since "24 hours ago" --no-pager 2>&1 \
  | rg -v 'session closed|session opened' | tail -50
sudo journalctl --since "24 hours ago" --no-pager 2>&1 \
  | rg -i 'oom|out of memory|ext4|I/O error|segfault|nginx: \[emerg\]|Accepted publickey' \
  | tail -40
```

### 14. Security sniff (non-invasive)

```bash
# failed ssh (if logs readable)
sudo journalctl -u ssh --since "24 hours ago" --no-pager 2>&1 \
  | rg -i 'Failed password|Invalid user' | tail -5
sudo journalctl -u ssh --since "24 hours ago" --no-pager 2>&1 \
  | rg -c 'Failed password|Invalid user' || true
# ufw if present
ufw status 2>/dev/null | head -20
```

Do not change firewall. High failure counts → mention, don't panic (bots are normal on public SSH).

---

## Report format (always)

Plain text, terminal-friendly. Lead with overall status.

```text
================================================================
VPS HEALTH  [ OK | WARN | CRIT ]    <hostname>    <UTC time>
================================================================
Uptime: … | Kernel: … | OS: … | Load: x x x (nproc=N) | NTP: …

OVERALL: one sentence (e.g. "WARN — RAM tight, reboot pending, disk OK")

================================================================
RESOURCES
================================================================
CPU:  load … vs N cores | top: proc1, proc2
RAM:  used/total | available … (WARN/CRIT?) | swap …
DISK: / use% avail | inodes | largest consumers (3–5 lines)
PRESSURE: psi / OOM events if any

================================================================
SERVICES
================================================================
system state: running|degraded|…
failed units: none | list
key: nginx=… docker=… postgres=… redis=… tailscaled=… ssh=…
reboot-required: yes/no (+ kernel pkgs summary)
needrestart: summary if available

================================================================
CONTAINERS / K8S
================================================================
Docker: N running, M exited, unhealthy: …
disk: docker system df one-liner
MicroK8s: running/skip | non-Running pods if any

================================================================
NETWORK
================================================================
eth0 IPs | tailscale IP | notable listens :22/:80/:443
ssh fails last 24h: count (if available)

================================================================
WEB / DATA
================================================================
nginx -t: ok/fail | certs expiring <14d: list or none
postgres/redis: up + brief size/mem

================================================================
ALERTS (prioritized)
================================================================
1. CRIT …
2. WARN …
3. INFO …

================================================================
RECOMMENDED NEXT ACTIONS (only if needed; ask before changing)
================================================================
- e.g. reboot window, add 1–2G swap, docker system prune, expand disk
- Point to nginx-certbot / tailscale-logs for specialized follow-up
```

---

## Interpreting common situations on this box

| Signal | Likely meaning | Direction |
|--------|----------------|-----------|
| Available RAM < ~1G on 8G host, no swap | OOM risk under spikes (Docker+k8s+node apps) | Identify top RSS; consider swapfile; reduce stacks |
| Load high, CPU top = node/java/k8s | App or cluster pressure | Per-service deep dive; don't reboot first |
| Disk 80%+ and `/var/lib/docker` huge | Images/build cache/logs | `docker system df`; prune only with approval |
| reboot-required + many linux-image pkgs | Kernels stacked, not rebooted in long uptime | Schedule reboot; confirm after |
| nginx ok but 502s | Upstream container/port down | Check `docker ps` + localhost curl; nginx-certbot skill |
| MicroK8s + Docker both heavy | Double container runtimes | Expected if user runs both; watch RAM |
| OOM killer in journal | Already crossed memory limit | Find victim PID/name; prevent recurrence |
| certbot timer failed | TLS expiry risk | nginx-certbot workflow G |
| Failed unit listed | Something broken at boot | `systemctl status UNIT` + journal |

---

## Optional one-shot script pattern (agent may run)

When you want a single collect pass:

```bash
echo '=== HOST ==='; date -u; hostname; uptime; nproc
echo '=== MEM ==='; free -h
echo '=== DISK ==='; df -hT; df -i | head -20
echo '=== FAILED ==='; systemctl --failed --no-pager
echo '=== REBOOT ==='; ls /var/run/reboot-required 2>/dev/null; head -20 /var/run/reboot-required.pkgs 2>/dev/null
echo '=== TOP CPU ==='; ps aux --sort=-%cpu | head -8
echo '=== TOP MEM ==='; ps aux --sort=-%mem | head -8
echo '=== DOCKER ==='; docker ps -a --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | head -25
echo '=== NGINX ==='; systemctl is-active nginx; sudo nginx -t 2>&1
echo '=== OOM ==='; sudo journalctl -k --since '7 days ago' --no-pager 2>&1 | rg -i 'oom|Killed process' | tail -15
```

Still format into the report template — never paste only raw script output to the user.

---

## What NOT to do

- Do not reboot, apt upgrade, or prune Docker without explicit user OK
- Do not disable MicroK8s/Docker to "fix" RAM without asking
- Do not open firewall holes or change SSH config during a health check
- Do not claim cloud-provider disk/CPU credits status without their API
- Do not treat high SSH brute-force counts alone as compromise
- Do not dump full `microk8s kubectl get all -A` (too noisy)

## Verification

A good health response:

1. Has an overall **OK/WARN/CRIT** label  
2. Includes RAM, disk, load, failed units, reboot-required at minimum  
3. Lists ≤10 concrete alerts/actions  
4. Uses live numbers from this run  
5. Separates "observe" from "change"  

## Related skills

- `nginx-certbot` — vhosts, TLS, renewals, 502 upstream mapping  
- `tailscale-logs` — tailnet peers, daemon logs, connectivity  
- `systematic-debugging` — when health check finds a deep app bug  
- `homepage-dashboard` — if homepage container is the focus  
