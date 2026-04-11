# DNF Tools

Tools for auditing DNF repository configuration and checking for available package updates on Rocky Linux 9/10.

| Tool | Script | Requires |
|------|--------|----------|
| Repo Health | `tools/dnf/repo-health.py` | `dnf` |
| Updates Available | `tools/dnf/updates-available.py` | `dnf` |

---

## repo-health.py

Enumerates all configured DNF repositories (enabled and disabled), tests network reachability of each enabled repo's base URL, and reports package counts. Useful for diagnosing repo issues on air-gapped or partially-connected systems.

### Syntax

```
python3 tools/dnf/repo-health.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Check all repos:**

```bash
python3 tools/dnf/repo-health.py
```

**JSON output:**

```bash
python3 tools/dnf/repo-health.py --json
```

**Show only unreachable repos:**

```bash
python3 tools/dnf/repo-health.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r['Network'] == 'unreachable':
        print('[WARN]', r['Repo ID'], '-', r['Name'])
"
```

**Count enabled repos:**

```bash
python3 tools/dnf/repo-health.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
enabled = [r for r in d['records'] if r['Enabled'] == 'yes']
print(f\"{len(enabled)} of {len(d['records'])} repos are enabled\")
"
```

### Sample Output

```
=================================
  DNF Repository Health
=================================

  Repo ID                         Name                            Enabled  Packages  Network       Status
  ──────────────────────────────  ──────────────────────────────  ───────  ────────  ────────────  ──────
  baseos                          Rocky Linux 9 - BaseOS          yes      2431      local/file    OK
  appstream                       Rocky Linux 9 - AppStream       yes      8762      local/file    OK
  extras                          Rocky Linux 9 - Extras          yes      87        local/file    OK
  epel                            Extra Packages for Enterprise.. yes      18342     reachable     OK
  updates                         Rocky Linux 9 - Updates         yes      312       local/file    OK
  gitlab-ce                       Gitlab CE Repository            yes      15        unreachable   WARN
  docker-ce-stable                Docker CE Stable                disabled 0         -             INFO
```

### Network Status Values

| Network Status | Meaning |
|----------------|---------|
| `reachable` | TCP connection to the repo's base URL host succeeded |
| `unreachable` | TCP connection to the repo's base URL host failed |
| `local/file` | Base URL is a `file://` path or `mirrorlist` — reachability not tested via TCP |
| `-` | Repo is disabled; reachability not checked |

### Status Column Values

| Status | Meaning |
|--------|---------|
| `OK` | Repo is enabled and reachable (or local) |
| `WARN` | Repo is enabled but appears unreachable over the network |
| `INFO` | Repo is disabled |

### Notes on Air-Gapped Systems

On air-gapped systems, enabled repos pointing to internet URLs will show `unreachable`. This is expected and not necessarily an error if you are using a local mirror with a `file://` baseurl or a Pulp/Satellite content server.

For clean output in air-gapped environments, either:
- Set `enabled=0` in the repo file for unused repos
- Or point repo baseurls to your local mirror server

`dnf repolist --verbose` can be slow on systems with many repos because it reads repo metadata. The tool has a 60-second timeout.

---

## updates-available.py

Lists available package updates and cross-references them with security advisories from `dnf updateinfo`. Groups output to show security updates prominently.

### Syntax

```
python3 tools/dnf/updates-available.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--security-only` | off | Show only updates with security advisories; skip bugfix and enhancement updates |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Show all available updates:**

```bash
python3 tools/dnf/updates-available.py
```

**Show only security updates:**

```bash
python3 tools/dnf/updates-available.py --security-only
```

**JSON output:**

```bash
python3 tools/dnf/updates-available.py --json
```

**Count security updates:**

```bash
python3 tools/dnf/updates-available.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
sec = [r for r in d['records'] if r['Advisory'] != '-']
print(f\"{len(sec)} security updates available\")
"
```

**List only Critical severity updates:**

```bash
python3 tools/dnf/updates-available.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r.get('Severity','').lower() == 'critical':
        print(r['Package'], r['Version'], r['Advisory'])
"
```

### Sample Output

**With updates available:**

```
====================================
  DNF Updates Available
====================================

  Total: 15   Security: 3

  Package             Version             Repo      Advisory       Severity    Status
  ──────────────────  ──────────────────  ────────  ─────────────  ──────────  ──────
  openssl             3.0.7-28.el9_4      baseos    RHSA-2026:1234  Important  WARN
  bind                9.16.23-14.el9_4    appstream RHSA-2026:5678  Moderate   WARN
  curl                7.76.1-29.el9_3     baseos    RHSA-2026:9012  Low        INFO
  python3             3.9.18-3.el9_4      baseos    -               -          INFO
  git                 2.43.0-1.el9        appstream -               -          INFO
```

**System is up to date:**

```
====================================
  DNF Updates Available
====================================

  System is up to date.
```

### Status Values

| Status | Meaning |
|--------|---------|
| `WARN` | Update has a security advisory with Important or Critical severity |
| `INFO` | Update is available (bugfix, enhancement, or low-severity security) |

### Advisory Severity Levels

Rocky Linux follows the Red Hat severity model:

| Severity | Description |
|----------|-------------|
| Critical | Remote code execution, privilege escalation — patch immediately |
| Important | Significant vulnerabilities — patch promptly |
| Moderate | Medium-impact issues |
| Low | Minor issues |

### Performance Note

`dnf check-update` and `dnf updateinfo` refresh metadata from repos on each run. On systems with many repos or slow mirrors this can take 30-90 seconds. The tool timeout is 120 seconds.

For air-gapped systems with no repo connectivity, these commands will fail or produce no output — the tool will report the system as up to date.

### Applying Updates

After reviewing:

```bash
# Apply all updates
sudo dnf update

# Apply only security updates
sudo dnf update --security

# Apply a specific package
sudo dnf update openssl

# Preview without applying
sudo dnf update --assumeno
```

### Cron Usage

```bash
# Weekly security update report
0 8 * * 1 root /usr/bin/python3 /home/mike/dev/lrn_tools/tools/dnf/updates-available.py \
    --security-only --json >> /var/log/lrn_tools/updates.log 2>&1
```
