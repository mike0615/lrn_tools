# System Tools

General-purpose Rocky Linux system information and troubleshooting tools.

| Tool | Script | Requires |
|------|--------|----------|
| System Info | `tools/system/sysinfo.py` | None (stdlib + `/proc`) |
| Service Status | `tools/system/service-status.py` | `systemctl` |
| Automated Triage | `tools/system/troubleshoot.py` | `systemctl`, `timedatectl`, `klist`, `ping` |

---

## sysinfo.py

Collects and displays comprehensive system information from a single host. Reads directly from `/proc` and the filesystem — no external commands except `hostname`, `df`, `getenforce`, and `timedatectl`.

### Syntax

```
python3 tools/system/sysinfo.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Display system info:**

```bash
python3 tools/system/sysinfo.py
```

**JSON output:**

```bash
python3 tools/system/sysinfo.py --json
```

**Extract just the OS and kernel version:**

```bash
python3 tools/system/sysinfo.py --json | \
    python3 -c "import json,sys; d=json.load(sys.stdin); r=d['records'][0]; print(r['os'], r['kernel'])"
```

### Sample Output

```
================================================
  System Info — ipa01.lrn.local
================================================

--- Identity ---
  Key           Value
  ────────────  ──────────────────────────────────────────────
  Hostname      ipa01
  FQDN          ipa01.lrn.local
  OS            Rocky Linux 9.7 (Blue Onyx)
  Kernel        5.14.0-611.41.1.el9_7.x86_64
  Uptime        14d 6h 32m 11s
  Load Avg      0.12 0.09 0.07
  Timezone      America/New_York
  NTP Synced    yes

--- Resources ---
  Key             Value
  ──────────────  ──────────────────────────────────────────────
  CPU Model       Intel(R) Xeon(R) E-2314 CPU @ 2.80GHz
  CPU Count       4
  RAM Total       31.2 GiB
  RAM Used        8.4 GiB
  RAM Available   22.8 GiB

--- Security ---
  Key      Value
  ───────  ───────────
  SELinux  Enforcing
  FIPS     Disabled

--- Disk Usage ---
  Mount   Size   Used   Avail  Use%  FSType
  ──────  ─────  ─────  ─────  ────  ──────
  /       50G    18G    32G    36%   xfs
  /boot   1.0G   312M   712M   31%   xfs
  /home   100G   45G    55G    45%   xfs
  /var    200G   80G    120G   40%   xfs
```

### JSON Record Schema

The JSON output contains two record types differentiated by the `section` field:

**System record (`section: "system"`):**

```json
{
  "section": "system",
  "hostname": "ipa01",
  "fqdn": "ipa01.lrn.local",
  "os": "Rocky Linux 9.7 (Blue Onyx)",
  "kernel": "5.14.0-611.41.1.el9_7.x86_64",
  "uptime": "14d 6h 32m 11s",
  "load_avg": "0.12 0.09 0.07",
  "cpu_model": "Intel(R) Xeon(R) E-2314",
  "cpu_count": "4",
  "ram_total": "31.2 GiB",
  "ram_used": "8.4 GiB",
  "ram_available": "22.8 GiB",
  "selinux": "Enforcing",
  "fips": "Disabled",
  "timezone": "America/New_York",
  "ntp_sync": "yes"
}
```

**Disk records (`section: "disk"`):** One per mounted filesystem, with fields `Mount`, `Size`, `Used`, `Avail`, `Use%`, `FSType`.

---

## service-status.py

Checks the active/failed state of a configured list of critical systemd services. Can also show all failed units system-wide.

### Syntax

```
python3 tools/system/service-status.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--service NAMES` | From `[services] critical_services` | Comma-separated list of service names to check. Overrides config. |
| `--all-failed` | off | Additionally show all failed units system-wide (runs `systemctl --failed`) |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Check all configured critical services:**

```bash
python3 tools/system/service-status.py
```

**Check specific services:**

```bash
python3 tools/system/service-status.py --service named,chronyd,sshd
```

**Show all failed units system-wide:**

```bash
python3 tools/system/service-status.py --all-failed
```

**Combine: check configured services AND show all failed:**

```bash
python3 tools/system/service-status.py --all-failed
```

**JSON output:**

```bash
python3 tools/system/service-status.py --json
```

**Use in a health check script:**

```bash
python3 tools/system/service-status.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
failed = [r for r in d['records'] if r['Status'] in ('ERROR', 'FAIL')]
if failed:
    print('FAILED SERVICES:')
    for f in failed: print(' ', f['Service'], '-', f['Active'])
    sys.exit(1)
print('All services OK')
"
```

### Sample Output

```
================================
  Service Status
================================

--- Critical Services (7 checked) ---
  Service          Active       Enabled   Status
  ───────────────  ──────────   ───────   ──────
  named            active       enabled   OK
  dirsrv@LRN-LOCAL active       enabled   OK
  krb5kdc          active       enabled   OK
  httpd            active       enabled   OK
  ipa              active       enabled   OK
  chronyd          active       enabled   OK
  firewalld        inactive     disabled  ERROR
```

### Service Name Format

Use the exact unit name as shown by `systemctl`. For parameterized units:

| Unit | Config value |
|------|-------------|
| Directory Service (standard) | `dirsrv.target` |
| Directory Service (IPA instance) | `dirsrv@LRN-LOCAL` |
| Named (BIND) | `named` |
| Kerberos KDC | `krb5kdc` |
| FreeIPA umbrella | `ipa` |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checked services are active |
| `2` | One or more services are in a warning state (activating, reloading) |
| `1` | One or more services are inactive or failed |

---

## troubleshoot.py

Automated triage tool that runs a structured set of diagnostic checks and presents a PASS/WARN/FAIL checklist. Useful as a first step when investigating connectivity or authentication issues in the LRN environment.

### Syntax

```
python3 tools/system/troubleshoot.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Run full triage:**

```bash
python3 tools/system/troubleshoot.py
```

**JSON output:**

```bash
python3 tools/system/troubleshoot.py --json
```

**Show only failures:**

```bash
python3 tools/system/troubleshoot.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r['Status'] == 'FAIL':
        print('[FAIL]', r['Check'], ':', r['Result'])
"
```

### Checks Performed

#### DNS Resolution

Attempts `socket.gethostbyname()` for several test hostnames:
- `google.com` (external resolution — reveals split-horizon or upstream issues)
- The configured IPA server hostname
- Up to 2 DNS server hostnames from config

#### Time Synchronization

- Queries `timedatectl` for `NTPSynchronized` status
- Reports current timezone
- If `chronyc` is available, reports the current time offset

#### Connectivity

Performs TCP connect tests to key IPA ports:

| Service | Port |
|---------|------|
| IPA LDAP | 389 |
| IPA LDAPS | 636 |
| IPA HTTPS | 443 |
| Kerberos KDC | 88 |
| DNS Primary | 53 |

#### Kerberos

Runs `klist -s` to check whether a valid TGT is present.

#### SELinux

Runs `getenforce` and reports the current mode. `Enforcing` = PASS, anything else = WARN.

#### Disk Space

Runs `df -h` and checks each mounted filesystem. Thresholds: >80% = WARN, >90% = FAIL.

### Sample Output

```
==================================
  Automated Triage
==================================

--- DNS Resolution ---
  Check                      Result           Status
  ─────────────────────────  ───────────────  ──────
  Resolve google.com         142.250.80.46    PASS
  Resolve ipa01.lrn.local    192.168.1.11     PASS
  Resolve 192.168.1.10       192.168.1.10     PASS

--- Time Sync ---
  Check            Result                    Status
  ───────────────  ────────────────────────  ──────
  NTP Synchronized yes                       PASS
  Timezone         America/New_York          INFO
  Chrony offset    -0.000123412 seconds      INFO

--- Connectivity ---
  Check                          Result       Status
  ─────────────────────────────  ──────────   ──────
  IPA LDAP (ipa01.lrn.local:389) reachable    PASS
  IPA LDAPS (ipa01.lrn.local:636)reachable    PASS
  IPA HTTPS (ipa01.lrn.local:443)reachable    PASS
  IPA Kerb  (ipa01.lrn.local:88) reachable    PASS
  DNS Primary (192.168.1.10:53)  reachable    PASS

--- Kerberos ---
  Check            Result                         Status
  ───────────────  ─────────────────────────────  ──────
  Kerberos ticket  Valid TGT present              PASS

--- SELinux ---
  Check         Result      Status
  ────────────  ──────────  ──────
  SELinux mode  Enforcing   PASS

--- Disk Space ---
  Check       Result  Status
  ──────────  ──────  ──────
  Disk /      36%     PASS
  Disk /boot  31%     PASS
  Disk /var   40%     PASS
```

### Status Values

| Status | Meaning |
|--------|---------|
| `PASS` | Check succeeded |
| `INFO` | Informational — not a pass/fail check |
| `WARN` | Something looks off but is not necessarily broken |
| `FAIL` | Check failed — investigate this item |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed or info-level |
| `2` | At least one WARN |
| `1` | At least one FAIL |

### Interpreting Results

| Symptom | Likely check to fail | Next step |
|---------|---------------------|-----------|
| Can't `kinit` | DNS Resolution, Connectivity:88 | Check DNS and firewall for Kerberos port |
| IPA web UI unreachable | Connectivity:443 | Check `httpd` service, firewall |
| LDAP auth failing | Connectivity:389/636 | Check `dirsrv`, TLS cert |
| Time drift errors | NTP Synchronized | `chronyc tracking`, fix NTP |
| SELinux denials | SELinux mode shows Permissive | Check `audit.log`, re-enable Enforcing |
