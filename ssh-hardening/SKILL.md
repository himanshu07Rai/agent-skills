---
name: ssh-hardening
description: "Audit and harden SSH and host edge access on Linux — sshd settings, keys, ufw/cloud firewall, fail2ban, lockout-safe procedures. Discover current config live."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ssh, hardening, security, ufw, fail2ban, firewall, keys]
    related_skills: [vps-health, tailscale-logs, systematic-debugging]
---

# SSH Hardening & Edge Access

Audit and safely harden OpenSSH and related host access controls. **Lockout prevention beats perfection.** Prefer drop-in configs, `sshd -t`, and keep an active session until a new login works.

## When to use

- Harden SSH / disable passwords / keys only
- Audit logins and brute-force noise
- Configure ufw or fail2ban
- New server baseline or suspected abuse (investigate first)

## Discover first (always)

Do not assume OS version, username, port, or current sshd flags.

```bash
date -u
whoami; id
hostnamectl 2>/dev/null | head -10 || true
systemctl is-active ssh 2>/dev/null || systemctl is-active sshd 2>/dev/null
# effective config
sudo sshd -T 2>/dev/null | rg '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|x11forwarding|maxauthtries|allowusers|allowgroups|clientaliveinterval|permitemptypasswords|authenticationmethods) '
ss -tlnp 2>/dev/null | rg 'sshd|ssh' || sudo ss -tlnp | rg 'sshd|:22\\b'
sudo ufw status verbose 2>/dev/null || echo 'ufw: n/a'
systemctl is-active fail2ban 2>/dev/null || echo 'fail2ban: not active'
ls -la ~/.ssh/ 2>/dev/null
# other users' authorized_keys counts only
sudo find /home /root -maxdepth 3 -name authorized_keys -printf '%p ' -exec wc -l {} \; 2>/dev/null
```

## Safety rules

1. **Never** set `PasswordAuthentication no` until key login works in a **second** session.
2. Keep the current SSH session open until verification succeeds.
3. Always `sudo sshd -t` before reload/restart.
4. Prefer `/etc/ssh/sshd_config.d/99-hardening.conf` over rewriting the main file.
5. Host firewall and **provider cloud firewall** are separate — both can lock you out. Confirm console/VNC/serial recovery exists before aggressive changes.
6. Do not delete the only `authorized_keys` entry.
7. Do not paste private keys into chat.
8. fail2ban can ban you — whitelist your admin IPs / private ranges when known.

---

## Workflow A — Security audit report

```bash
date -u
echo '=== EFFECTIVE SSHD ==='
sudo sshd -T | rg '^(port|addressfamily|listenaddress|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|x11forwarding|allowtcpforwarding|permitemptypasswords|maxauthtries|logingracetime|clientaliveinterval|clientalivecountmax|allowusers|allowgroups|authenticationmethods|gatewayports) '

echo '=== CONFIG FILES ==='
ls -la /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null
sudo rg -n '^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|Port |AllowUsers|Include)' \
  /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null

echo '=== LISTEN ==='
ss -tlnp | rg 'sshd|:22\\b' || sudo ss -tlnp | rg 'sshd|:22\\b'

echo '=== AUTH RECENT ==='
# unit may be ssh or sshd
for u in ssh sshd; do
  sudo journalctl -u "$u" --since '7 days ago' --no-pager 2>/dev/null \
    | rg -i 'Accepted|Failed password|Invalid user' | tail -40
done
echo -n 'failed≈ '; sudo journalctl -u ssh -u sshd --since '7 days ago' --no-pager 2>/dev/null | rg -c 'Failed password' || true
echo -n 'accepted≈ '; sudo journalctl -u ssh -u sshd --since '7 days ago' --no-pager 2>/dev/null | rg -c 'Accepted' || true

echo '=== FIREWALL / F2B ==='
sudo ufw status verbose 2>/dev/null || true
sudo fail2ban-client status 2>/dev/null || echo 'fail2ban: none'
```

### Report shape

```text
================================================================
SSH / EDGE AUDIT
================================================================
port | password auth | root login | pubkey | x11 | maxauthtries

================================================================
ACCESS PATHS
================================================================
public SSH | alternate admin path (VPN/console)? 

================================================================
FIREWALL
================================================================
host fw state | notes on provider fw if unknown

================================================================
THREAT SIGNALS
================================================================
failed vs accepted counts | odd Accepted sources

================================================================
GAPS vs BASELINE
================================================================
ordered recommendations (lockout-safe)
```

---

## Workflow B — Prove key login before disabling passwords

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys 2>/dev/null
wc -l ~/.ssh/authorized_keys
rg -n '^(ssh-ed25519|ssh-rsa|ecdsa-sha2|sk-ssh-ed25519)' ~/.ssh/authorized_keys | head
```

User verifies from a **new** client session:

```bash
ssh -o PreferredAuthentications=publickey -o PasswordAuthentication=no USER@HOST
```

Add a key (public half only):

```bash
umask 077
mkdir -p ~/.ssh
echo 'ssh-ed25519 AAAA... comment' >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

---

## Workflow C — Baseline hardening drop-in

```bash
sudo cp -a /etc/ssh/sshd_config "/etc/ssh/sshd_config.bak.$(date +%Y%m%d%H%M%S)"
sudo mkdir -p /etc/ssh/sshd_config.d
```

Write `/etc/ssh/sshd_config.d/99-hardening.conf` (adjust only after discovery):

```text
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 4
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
# Optional after confirming username(s):
# AllowUsers youruser
```

```bash
sudo sshd -t && sudo systemctl reload ssh 2>/dev/null || sudo systemctl reload sshd
sudo sshd -T | rg '^(passwordauthentication|permitrootlogin|x11forwarding|maxauthtries) '
```

Keep old session open → test new login → if fail, remove drop-in and reload.

---

## Workflow D — UFW baseline (explicit user OK)

```bash
sudo ufw status
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
# only if this host serves the public web:
# sudo ufw allow 80/tcp
# sudo ufw allow 443/tcp
sudo ufw show added
# enable only after review:
# sudo ufw --force enable
sudo ufw status verbose
```

Note: Docker `0.0.0.0` publishes may bypass ufw depending on iptables integration — prefer binding services to `127.0.0.1` or a private IP (see docker skills).

---

## Workflow E — fail2ban for sshd (optional)

```bash
sudo apt-get update && sudo apt-get install -y fail2ban   # Debian/Ubuntu; adapt for other distros
sudo systemctl enable --now fail2ban
```

`/etc/fail2ban/jail.d/sshd.local`:

```text
[sshd]
enabled = true
port = ssh
filter = sshd
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
# ignoreip = 127.0.0.1/8 ::1 100.64.0.0/10 ADMIN_IP
```

```bash
sudo fail2ban-client reload
sudo fail2ban-client status sshd
# unban: sudo fail2ban-client set sshd unbanip IP
```

---

## Workflow F — Login review (read-only)

```bash
last -n 30 2>/dev/null
sudo lastb -n 20 2>/dev/null | head -20
sudo journalctl -u ssh -u sshd --since '24 hours ago' --no-pager 2>/dev/null \
  | rg 'Accepted (publickey|password)'
```

Bot `Failed password` noise is normal on public :22. Unexpected **Accepted** sources deserve attention.

---

## Baseline target

| Control | Target |
|---------|--------|
| PasswordAuthentication | no (after key proven) |
| PermitRootLogin | prohibit-password or no |
| PubkeyAuthentication | yes |
| Empty passwords | no |
| X11Forwarding | no on servers |
| MaxAuthTries | 3–6 |
| Host or cloud FW | SSH + only needed ports |
| fail2ban sshd | optional on public SSH |
| `.ssh` / `authorized_keys` perms | 700 / 600 |

## What NOT to do

- Disable passwords before a successful key-only test login
- `ufw enable` without allowing SSH
- Rely on port changes alone as security
- Remove alternate console/VPN access before hardening is verified
- Store user private keys on the server for inbound login

## Verification

1. `sshd -t` OK; ssh service active  
2. New key-only session works  
3. Password auth fails if disabled  
4. Firewall (if enabled) allows admin access  
5. Residual risks documented  

## Related

- `vps-health` — host context  
- `tailscale-logs` — private admin path  
- `docker-stack` / `docker-compose` — reduce public port surface  
