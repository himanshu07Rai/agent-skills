---
name: tailscale-logs
description: "Check Tailscale status, journal logs, peer activity, and connectivity on this host/tailnet."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [tailscale, vpn, networking, logs, diagnostics, peer-status]
    related_skills: [systematic-debugging]
---

# Tailscale Logs & Network Activity

Diagnose Tailscale on the local host: daemon health, peer status, recent journal activity, traffic, and live connectivity. Produce a concise human-readable report.

## When to use

- User asks to check Tailscale logs, status, peers, or recent network activity
- Connectivity issues between tailnet machines
- After re-auth, key expiry, or unexpected logout
- "Who is online / what's talking to this box over Tailscale?"

## Prerequisites

```bash
which tailscale
tailscale version
# Prefer sudo for journal + /var/lib/tailscale (journal often needs adm/root)
```

If `tailscale` is missing: install per https://tailscale.com/download then re-run.

## Workflow (run in order)

### 1. Quick status snapshot

```bash
date -u
tailscale status
tailscale ip -4
tailscale ip -6 2>/dev/null || true
```

Interpret columns: IP, hostname, user, OS, connection state (`active; direct …`, idle `-`, offline timestamps).

### 2. JSON status (peer detail)

```bash
tailscale status --json
```

Extract per node:
- HostName, DNSName, OS, TailscaleIPs
- Online, Active, Relay, CurAddr
- RxBytes / TxBytes, LastHandshake, LastSeen, LastWrite
- Created, KeyExpiry
- CurrentTailnet.Name, MagicDNSSuffix
- Self capabilities (is-admin, is-owner, ssh, etc.)

Do **not** dump full JSON to the user — summarize into a table.

### 3. Local daemon logs (primary activity source)

Journal is the main log on Linux systemd hosts:

```bash
# Last 24h key events (filter noise)
sudo journalctl -u tailscaled --since "24 hours ago" --no-pager 2>&1 \
  | rg -i 'login|auth|Starting|Running|authorized|Register|error|warn|active login|userspace WireGuard|SSH|file|disco: node|exit|NeedsLogin|nodeKey|Generating|logtail.*fail|PollNetMap|GOAWAY|bugreport' \
  | rg -v 'RTM_|LinkChange|portUpdate|dns: Set|dns: Resolver|dns: OScfg|monitor:|router: portUpdate|cali|vxlan|br-' \
  | tail -150

# Longer timeline (7d) — high-signal only
sudo journalctl -u tailscaled --since "7 days ago" --no-pager -o short-iso 2>&1 \
  | rg -i 'Switching ipn|active login|machineAuthorized|AuthURL|got response|peerapi|Configuring userspace|error:|Received error|logtail.*fail|nodekey|Generating|NeedsLogin|nodeKeyExpired' \
  | tail -80
```

If sudo is unavailable:
```bash
journalctl -u tailscaled --since "24 hours ago" --no-pager 2>&1 | tail -100
# May be empty without adm/systemd-journal group — say so explicitly
```

Optional on-disk logs (often empty; logtail ships to Tailscale cloud):
```bash
sudo ls -la /var/lib/tailscale/
sudo tail -n 50 /var/lib/tailscale/tailscaled.log1.txt /var/lib/tailscale/tailscaled.log2.txt 2>/dev/null
```

### 4. Metrics + prefs (traffic + config)

```bash
tailscale metrics 2>&1 | head -80
tailscale debug prefs 2>&1
tailscale lock status 2>&1
```

From metrics, report:
- inbound/outbound bytes by path: `derp`, `direct_ipv4`, `direct_ipv6`
- dropped packets
- home DERP region id
- health warning count

From prefs: WantRunning, RunSSH, ExitNode, AdvertiseRoutes, ShieldsUp, LoggedOut, CorpDNS, AutoUpdate.

### 5. Live connectivity checks

Ping every peer from `tailscale status` (cap at ~10 peers):

```bash
# Replace HOST with MagicDNS short name or 100.x IP
tailscale ping --c 3 HOST
```

Note path: `via DERP(region)` vs `via IP:port` (direct) and RTT.

Optional net path quality:
```bash
tailscale netcheck 2>&1 | head -40
```

### 6. Optional: correlate host auth with Tailscale IPs

If investigating who SSHed in over the tailnet:

```bash
# Tailscale CGNAT is 100.64.0.0/10
sudo rg '100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\.' /var/log/auth.log 2>/dev/null | tail -40
# or
sudo journalctl -u ssh --since "7 days ago" --no-pager 2>&1 | rg '100\.' | tail -40
```

Map IPs back with:
```bash
tailscale whois 100.x.y.z
```

### 7. Report format (always use this shape)

Plain text, terminal-friendly:

```
================================================================
TAILNET OVERVIEW
================================================================
Tailnet / MagicDNS / this node / IP / version / state / home DERP /
public endpoint / SSH / exit node / routes / lock / key expiry / check time

================================================================
DEVICES
================================================================
Table: IP | hostname | OS | status (online/active/path)

================================================================
LIVE CONNECTIVITY
================================================================
Per-peer ping: RTT + direct vs DERP

================================================================
TRAFFIC (since node up / from metrics + peer Rx/Tx)
================================================================
Who has bytes; path mix (direct v4/v6 vs DERP)

================================================================
RECENT ACTIVITY TIMELINE
================================================================
Chronological high-signal journal events (re-auth, peer joins,
key expiry, errors). Skip disco keepalive spam unless diagnosing
path flaps.

================================================================
LIMITS
================================================================
Local logs = this node's view only.
Full admin audit (ACL changes, device approvals, API keys):
  https://login.tailscale.com/admin/machines
  https://login.tailscale.com/admin/logs
```

## Interpreting common signals

| Signal | Meaning |
|--------|---------|
| `NeedsLogin` / AuthURL | Node logged out or needs re-auth |
| `nodeKeyExpired=true` then new key | Key rotated; may need re-approval |
| `machineAuthorized=true` | Control plane accepted the node |
| `active; direct …` | Live data path, peer-to-peer |
| `via DERP(blr)` etc. | Relayed; NAT/firewall blocked direct |
| Peer count 2→3 in Reconfig | New peer appeared in netmap |
| `disco: node […] now using IP` | Path discovery / endpoint change (noisy; summarize) |
| `PollNetMap … GOAWAY/context canceled` | Transient control-plane blip; OK if recovered |
| `logtail … 429` | Cloud log upload rate-limit; local ops fine |
| `http 410: auth path not found` | Stale auth URL; retry login usually succeeds |
| Rx/Tx on one peer only | That machine is the active session |

## What NOT to do

- Do not paste full `status --json` or raw multi-thousand-line journals at the user
- Do not run `tailscale bugreport` unless debugging with Tailscale support (creates support artifacts)
- Do not claim full tailnet audit coverage from local logs alone
- Do not print private keys / full prefs secrets (prefs may redact; still avoid dumping Config.PrivateNodeKey)
- Skip `sudo tailscale debug netmap` unless needed — noisy and often root-gated

## macOS notes

- Logs: `log show --predicate 'subsystem == "com.tailscale.tailscaled"' --last 1d` (or Console.app)
- Prefer `tailscale status` / `tailscale ping` same as Linux
- No systemd journal

## Windows notes (remote peer only from this skill’s host)

This skill targets the machine where the agent runs. For a Windows peer’s own logs, user must check that device; from Linux you only see disco/peer bytes toward it.

## Verification

After the report:
1. `tailscale status` shows BackendState Running (or explain if not)
2. Every listed peer has a ping result or explicit unreachable reason
3. Timeline covers at least the last re-auth / restart if any in the last 7 days
4. User is pointed at admin console for anything local logs cannot show
