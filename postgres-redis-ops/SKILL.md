---
name: vps-health
description: "Check Linux VPS/server health — CPU, RAM, disk, load, failed units, reboot-needed, optional Docker/k8s/nginx/DB — traffic-light report. Discover stacks live; no fixed inventory."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vps, health, monitoring, disk, memory, cpu, docker, systemd, diagnostics]
    related_skills: [nginx-certbot, tailscale-logs, docker-stack, postgres-redis-ops, systematic-debugging]
---

# VPS / Server Health Check

Fast, structured health audit of the **local** Linux host. Prefer **summary + alerts** over raw dumps. Discover which stacks exist; skip missing ones. Do not bake in hostnames, container lists, or service inventories.

## When to use

- "Is the server OK?", slow box, disk/RAM/CPU check
- After deploys, crashes, OOM suspicion, before/after reboot
- Periodic sanity check

## Principles

1. Measure live — never reuse stale resource numbers from skill text.
2. Discover optional components (`docker`, `nginx`, `psql`, `microk8s`, `tailscale`) via `command -v` / `systemctl`.
3. Cap process lists (top ~8–10) and journal noise.
4. Read-only by default — no reboot/prune/upgrade unless asked.

## Safety

- Do not dump full `docker inspect`, full `ps`, or multi-MB logs.
- Do not print secrets from env files or container configs.
- If sudo fails, say what could not be checked.

## Thresholds (defaults)

| Metric | OK | WARN | CRIT |
|--------|----|------|------|
| Root disk use% | < 75% | 75–90% | ≥ 90% or Avail < 2G |
| Inode use% | < 80% | 80–95% | ≥ 95% |
| Memory available | > 15% of total | 10–15% | < 10% or < 300Mi |
| Swap used (if any) | < 50% | 50–80% | ≥ 80% or thrashing |
| Load avg (1m) | < nproc | nproc–2×nproc | > 2×nproc sustained |
| Failed systemd units | 0 | — | ≥ 1 |
| `/var/run/reboot-required` | absent | present | present + stacked kernels |
| Docker unhealthy (if docker) | 0 | 1–2 | many / restart loops |
| nginx -t (if nginx) | ok | — | fail |
| Clock sync | synchronized | — | unsynchronized |

"Available" memory = `free` **available** column, not only "free".

---

## Workflow (one pass)

### 1. Identity & uptime

```bash
date -u
hostnamectl 2>/dev/null || hostname
rg -n '^(NAME|VERSION|VERSION_ID)=' /etc/os-release
uname -r
uptime
who -b 2>/dev/null
timedatectl 2>/dev/null | rg 'Local time|Time zone|synchronized|NTP' || true
```

### 2. CPU & load

```bash
nproc
uptime
ps aux --sort=-%cpu | head -n 11
command -v vmstat >/dev/null && vmstat 1 3
```

Note high `st` (steal) on cloud VMs when present.

### 3. Memory & swap

```bash
free -h
ps aux --sort=-%mem | head -n 11
swapon --show
cat /proc/pressure/memory 2>/dev/null
sudo journalctl -k --since '7 days ago' --no-pager 2>&1 \
  | rg -i 'Out of memory|Killed process|oom-kill|Memory cgroup' | tail -30
```

If no swap and available RAM is WARN/CRIT → highlight OOM risk.

### 4. Disk & inodes

```bash
df -hT
df -i
sudo du -xh / --max-depth=1 2>/dev/null | sort -hr | head -n 15
# optional growth points if they exist
sudo du -sh /var/lib/docker /var/log /var/lib/containerd /snap \
  /var/cache/apt /var/lib/postgresql 2>/dev/null
journalctl --disk-usage 2>/dev/null
```

### 5. Systemd

```bash
systemctl is-system-running 2>/dev/null
systemctl --failed --no-pager
# probe common units only if present — do not invent a fixed app list
for u in nginx docker containerd ssh sshd cron crond \
         postgresql redis-server redis tailscaled \
         unattended-upgrades certbot.timer; do
  systemctl status "$u" --no-pager -n 0 2>/dev/null | head -1 || true
  state=$(systemctl is-active "$u" 2>/dev/null) || continue
  en=$(systemctl is-enabled "$u" 2>/dev/null || echo n/a)
  printf '%-32s %s (%s)\n' "$u" "$state" "$en"
done
```

### 6. Reboot / updates pending

```bash
ls -la /var/run/reboot-required 2>/dev/null || echo 'no reboot-required flag'
head -40 /var/run/reboot-required.pkgs 2>/dev/null
echo "running_kernel=$(uname -r)"
ls -1 /boot/vmlinuz-* 2>/dev/null | tail -5
command -v needrestart >/dev/null && (sudo needrestart -b 2>/dev/null | head -40)
```

Do not reboot unless asked.

### 7. Network (summary)

```bash
ip -br a 2>/dev/null | head -30
ip route | head -8
ss -s 2>/dev/null
# sample common admin/web ports if listening — not an inventory of apps
sudo ss -tlnp 2>/dev/null | rg ':(22|80|443)\\s' | head -20
curl -4 -s --max-time 3 ifconfig.me 2>/dev/null; echo
```

### 8. Docker (if installed)

```bash
if command -v docker >/dev/null; then
  docker info 2>/dev/null | rg -i 'Server Version|Containers:|Running:|Stopped:|Images:|ERROR'
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -40
  docker ps -a --filter health=unhealthy --format '{{.Names}} {{.Status}}'
  docker system df 2>/dev/null
fi
```

Deep container work → `docker-stack`.

### 9. Kubernetes / MicroK8s (if present)

```bash
if command -v microk8s >/dev/null; then
  microk8s status 2>/dev/null | head -30
  microk8s kubectl get nodes 2>/dev/null
  microk8s kubectl get pods -A 2>/dev/null | rg -v 'Running|Completed' | head -25
elif command -v kubectl >/dev/null; then
  kubectl get nodes 2>/dev/null
  kubectl get pods -A 2>/dev/null | rg -v 'Running|Completed' | head -25
fi
```

### 10. Data stores (if present)

```bash
systemctl is-active postgresql 2>/dev/null
systemctl is-active redis-server 2>/dev/null || systemctl is-active redis 2>/dev/null
# light only — details in postgres-redis-ops
sudo -u postgres psql -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datistemplate=false ORDER BY 2;" 2>/dev/null | head -20
redis-cli ping 2>&1 | head -2
```

### 11. Nginx / certs (if present)

```bash
if command -v nginx >/dev/null; then
  systemctl is-active nginx 2>/dev/null
  sudo nginx -t 2>&1
  ls /etc/nginx/sites-enabled 2>/dev/null | head -30
fi
command -v certbot >/dev/null && sudo certbot certificates 2>/dev/null \
  | rg -i 'Certificate Name|Expiry Date|INVALID|ERROR' | head -40
```

Deep TLS/vhost work → `nginx-certbot`.

### 12. Tailscale one-liner (if present)

```bash
command -v tailscale >/dev/null && tailscale status 2>/dev/null | head -15
```

Full audit → `tailscale-logs`.

### 13. Recent critical logs

```bash
sudo journalctl -p err..alert --since '24 hours ago' --no-pager 2>&1 \
  | rg -v 'session closed|session opened' | tail -40
sudo journalctl --since '24 hours ago' --no-pager 2>&1 \
  | rg -i 'oom|out of memory|I/O error|segfault|nginx: \[emerg\]' | tail -30
```

### 14. Light SSH noise (optional)

```bash
sudo journalctl -u ssh -u sshd --since '24 hours ago' --no-pager 2>/dev/null \
  | rg -c 'Failed password|Invalid user' || true
```

Do not treat bot noise alone as compromise.

---

## Report format

```text
================================================================
VPS HEALTH  [ OK | WARN | CRIT ]    <hostname>    <UTC>
================================================================
Uptime | kernel | OS | load (nproc=N) | NTP

OVERALL: one sentence

================================================================
RESOURCES
================================================================
CPU / RAM / DISK / pressure / OOM

================================================================
SERVICES
================================================================
system state | failed units | key discovered services | reboot-required

================================================================
OPTIONAL STACKS
================================================================
Docker / k8s / nginx / DB / tailscale — only sections that exist

================================================================
ALERTS (prioritized)
================================================================
================================================================
NEXT ACTIONS (ask before changing)
================================================================
```

## What NOT to do

- Embed a permanent inventory of this machine's containers or apps in the skill
- Reboot, prune, or upgrade without OK
- Claim provider-panel status without their API
- Dump entire process tables or kube all-namespaces by default

## Verification

1. Overall OK/WARN/CRIT label  
2. Live RAM, disk, load, failed units, reboot flag at minimum  
3. ≤10 concrete alerts/actions  
4. Observe vs change clearly separated  

## Related

- `docker-stack`, `nginx-certbot`, `postgres-redis-ops`, `tailscale-logs`, `ssh-hardening`
