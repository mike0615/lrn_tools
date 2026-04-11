# Log Tools

Tools for querying the systemd journal and scanning log files for errors, warnings, and custom patterns.

| Tool | Script | Requires |
|------|--------|----------|
| Journal Errors | `tools/logs/journal-errors.py` | `journalctl` |
| Log Summary | `tools/logs/log-summary.py` | Read access to log files |

---

## journal-errors.py

Queries the systemd journal for all entries at priority `err` (3) or higher — ERROR and CRITICAL — within a configurable time window. Groups results by systemd unit and reports the error count and the most recent message for each unit.

### Syntax

```
python3 tools/logs/journal-errors.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--hours N` | `24` | How far back to look in the journal, in hours |
| `--unit UNIT` | _(all units)_ | Filter to a specific systemd unit name (e.g. `named`, `httpd`, `dirsrv@LRN-LOCAL`) |
| `--top N` | `20` | Show the top N units by error count (units with more errors appear first) |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Default — last 24 hours, all units, top 20:**

```bash
python3 tools/logs/journal-errors.py
```

**Last 7 days of errors:**

```bash
python3 tools/logs/journal-errors.py --hours 168
```

**Errors from a specific unit:**

```bash
python3 tools/logs/journal-errors.py --unit named
python3 tools/logs/journal-errors.py --unit dirsrv@LRN-LOCAL
python3 tools/logs/journal-errors.py --unit httpd
```

**Show top 5 noisiest units:**

```bash
python3 tools/logs/journal-errors.py --top 5
```

**JSON output:**

```bash
python3 tools/logs/journal-errors.py --json
```

**Get units with more than 100 errors:**

```bash
python3 tools/logs/journal-errors.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if int(r['Error Count']) >= 100:
        print(r['Error Count'].rjust(6), r['Unit'])
"
```

**Get raw journal messages for a specific unit:**

```bash
# Use journalctl directly once you've identified the unit
journalctl -u named --since "24 hours ago" --priority=err --no-pager
```

### Sample Output

```
======================================
  Journal Errors — Last 24 Hours
======================================

  Total error entries: 47   Affected units: 3

  Unit                      Error Count  Last Message                                    Status
  ────────────────────────  ───────────  ──────────────────────────────────────────────  ──────
  named.service             32           zone lrn.local/IN: loading from master file ... WARN
  dirsrv@LRN-LOCAL.service  12           Could not obtain a certificate: ...             WARN
  chronyd.service           3            Can't synchronise: no reachable sources         INFO
```

**No errors found:**

```
======================================
  Journal Errors — Last 1 Hours
======================================

  No error-level journal entries found in this window.
```

### Status Values

| Status | Meaning |
|--------|---------|
| `WARN` | Unit produced 10 or more error entries in the window |
| `INFO` | Unit produced fewer than 10 errors — noteworthy but not alarming |

### Understanding Journal Priority Levels

The tool filters at `--priority=err` which captures:

| Priority | Level | Description |
|----------|-------|-------------|
| 0 | emerg | System is unusable |
| 1 | alert | Action must be taken immediately |
| 2 | crit | Critical conditions |
| 3 | err | Error conditions |

Priorities 4 (warning), 5 (notice), 6 (info), and 7 (debug) are excluded.

### Common Units to Watch

| Unit | What errors indicate |
|------|---------------------|
| `named.service` | Zone transfer failures, DNSSEC issues, config errors |
| `dirsrv@LRN-LOCAL.service` | LDAP replication issues, TLS cert problems |
| `krb5kdc.service` | Kerberos authentication failures |
| `httpd.service` | IPA web UI errors, TLS cert issues |
| `chronyd.service` | NTP source unreachable |
| `firewalld.service` | Rule application failures |
| `sssd.service` | SSSD cache/auth failures |
| `sshd.service` | Authentication failures (covered better by `log-summary.py` on `/var/log/secure`) |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No error entries found |
| `2` | Error entries found (non-zero count) |
| `1` | Tool error (journalctl failed) |

### Cron Usage

```bash
# Daily error digest
0 8 * * * root /usr/bin/python3 /home/mike/dev/lrn_tools/tools/logs/journal-errors.py \
    --hours 24 --json >> /var/log/lrn_tools/journal-errors.log 2>&1
```

---

## log-summary.py

Scans text log files using regular expression patterns and produces a frequency table of matches sorted by count. Useful for monitoring FreeIPA access logs, BIND query logs, authentication logs, and custom application logs that are not in the systemd journal.

### Syntax

```
python3 tools/logs/log-summary.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--file PATH` | From `[logs] watch_files` | Log file to scan. Can be specified multiple times. Overrides config when used. |
| `--pattern NAME=REGEX` | From `[logs] patterns` + built-ins | Additional regex pattern in `name=regex` format. Can be specified multiple times. |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Scan all configured log files with all patterns:**

```bash
python3 tools/logs/log-summary.py
```

**Scan a specific log file:**

```bash
python3 tools/logs/log-summary.py --file /var/log/secure
```

**Scan multiple files:**

```bash
python3 tools/logs/log-summary.py \
    --file /var/log/messages \
    --file /var/log/secure \
    --file /var/log/named/query.log
```

**Add a custom pattern on the command line:**

```bash
python3 tools/logs/log-summary.py --pattern "kerberos_fail=krb5kdc.*failed"
```

**Combine a specific file with a custom pattern:**

```bash
python3 tools/logs/log-summary.py \
    --file /var/log/dirsrv/slapd-LRN-LOCAL/access \
    --pattern "bind_op=BIND" \
    --pattern "search_op=SRCH"
```

**JSON output:**

```bash
python3 tools/logs/log-summary.py --json
```

**Get patterns with more than 100 matches:**

```bash
python3 tools/logs/log-summary.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if int(r['Count']) >= 100:
        print(f\"{r['Count']:>6}  {r['File']}  {r['Pattern']}\")
"
```

### Sample Output

```
=================================
  Log Summary
=================================

  Files scanned: 3   Patterns: 8

  File       Pattern       Count  Sample                                            Status
  ─────────  ────────────  ─────  ────────────────────────────────────────────────  ──────
  secure     Auth Failure  847    Mar 15 09:32:11 host sshd[12345]: Failed passwo   WARN
  messages   WARNING       312    Apr 11 08:00:01 host chronyd[567]: Can't synch    INFO
  messages   ERROR         47     Apr 11 06:15:22 host named[890]: zone lrn.loca    INFO
  access     Denied        23     [11/Apr/2026:10:00:00] conn=1234 op=2 RESULT e    INFO
  messages   CRITICAL      2      Apr 11 03:00:00 host kernel: Out of memory: K    WARN

--- Errors ---
  Permission denied: /var/log/audit/audit.log
```

### Status Values

| Status | Meaning |
|--------|---------|
| `WARN` | Pattern matched 50 or more times in the file |
| `INFO` | Pattern matched 10-49 times |
| `OK` | Pattern matched fewer than 10 times |

Thresholds are internal to the tool. They are intentionally conservative — a high count of `Auth Failure` in `/var/log/secure` almost certainly warrants attention.

### Built-in Patterns

These patterns are always applied and cannot be disabled:

| Pattern Name | Regex |
|-------------|-------|
| ERROR | `\bERROR\b\|\berror\b` |
| WARNING | `\bWARN(ING)?\b` |
| CRITICAL | `\bCRITICAL\b\|\bCRIT\b` |
| Auth Failure | `authentication failure\|Failed password\|Invalid user` |
| Denied | `\bDENIED\b\|\bdenied\b` |
| Segfault | `\bsegfault\b\|\bsegmentation fault\b` |

### Custom Patterns in Config

Add site-specific patterns to the config file:

```ini
[logs]
patterns =
    ipa_repl_fail=replica.*failed,
    ldap_bind_fail=BIND.*err=49,
    named_refused=REFUSED,
    my_app_exception=MyApplication.*Exception
```

These are appended to the built-in patterns. Both are applied to every scanned file.

### Useful Log Files for the LRN

| Log File | What to find there |
|----------|-------------------|
| `/var/log/messages` | General system messages, kernel, named |
| `/var/log/secure` | SSH auth attempts, sudo, PAM events |
| `/var/log/named/query.log` | BIND DNS query log (if query logging is enabled) |
| `/var/log/named/named.log` | BIND named operational log |
| `/var/log/dirsrv/slapd-LRN-LOCAL/access` | IPA LDAP access log |
| `/var/log/dirsrv/slapd-LRN-LOCAL/error` | IPA LDAP error log |
| `/var/log/httpd/error_log` | IPA web UI / Apache errors |
| `/var/log/krb5kdc.log` | Kerberos KDC log |
| `/var/log/pki/pki-tomcat/ca/system` | IPA CA system log |

### Performance Note

The tool reads each log file entirely into memory line-by-line. For very large log files (>500 MB), this may be slow. Rotate logs regularly with `logrotate` to keep file sizes manageable. The tool has no size limit or timeout — it will complete even on large files, just more slowly.

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Scan completed (whether or not matches were found) |
| `2` | High-count pattern matches found (WARN threshold reached) |
| `1` | Tool error (could not read any log files) |
