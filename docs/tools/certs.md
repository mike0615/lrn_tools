# Certificate Tools

Tools for inventorying and monitoring TLS/SSL certificates across the LRN environment.

| Tool | Script | Requires |
|------|--------|----------|
| Certificate Inventory | `tools/certs/cert-inventory.py` | `openssl` |
| Expiry Check | `tools/certs/cert-expiry-check.py` | `openssl` |

Both tools use `openssl x509` via subprocess — no Python crypto libraries required.

---

## cert-inventory.py

Scans one or more directories and files for PEM-format certificates and reports detailed information for each: Common Name, Subject Alternative Names, issuer, expiry date, and days remaining. Intended for a full inventory and audit view.

### Syntax

```
python3 tools/certs/cert-inventory.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path PATH` | From `[certs] scan_paths` | Additional path (file or directory) to scan. Can be specified multiple times. |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Scan paths configured in config.ini:**

```bash
python3 tools/certs/cert-inventory.py
```

**Add an extra directory:**

```bash
python3 tools/certs/cert-inventory.py --path /opt/myapp/certs
```

**Scan multiple extra paths:**

```bash
python3 tools/certs/cert-inventory.py \
    --path /opt/nginx/ssl \
    --path /etc/haproxy/certs
```

**JSON output:**

```bash
python3 tools/certs/cert-inventory.py --json
```

**Find all certs expiring in the next 90 days:**

```bash
python3 tools/certs/cert-inventory.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
expiring = [r for r in d['records'] if r.get('Days Left','').lstrip('-').isdigit()
            and int(r['Days Left']) < 90]
for r in expiring:
    print(r['Days Left'].rjust(5), 'days:', r['File'], '-', r['CN'])
"
```

### Sample Output

```
=================================
  Certificate Inventory
=================================

  Scanned 6 certificate files in 3 path(s)

  File             CN                             Expires                    Days Left  Status
  ───────────────  ─────────────────────────────  ─────────────────────────  ─────────  ──────
  ca.crt           Certificate Authority           Jan  1 00:00:00 2028 GMT   648        OK
  lrn.local.crt    ipa01.lrn.local                 Apr 11 00:00:00 2027 GMT   365        OK
  webserver.crt    webserver.lrn.local             May  1 00:00:00 2026 GMT   20         WARN
  expired.crt      old-server.lrn.local            Jan  1 00:00:00 2025 GMT   -100       CRIT

--- Parse Errors ---
  Could not parse: /etc/pki/tls/certs/ca-bundle.trust.crt
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Cert expires more than `warn_days` days from now (default: 30) |
| `WARN` | Cert expires within `warn_days` days |
| `CRIT` | Cert expires within `critical_days` days (default: 7) |

Thresholds are configurable in `[certs] warn_days` and `[certs] critical_days`.

### Scan Behavior

- Directories are searched recursively for `*.pem`, `*.crt`, and `*.cer` files
- Both PEM (`-----BEGIN CERTIFICATE-----`) and DER format files are attempted
- Files that fail parsing (e.g., private keys, PKCS12 bundles, CA trust bundles) are listed under **Parse Errors** but do not cause the tool to fail
- Duplicate paths (if a file is listed in multiple scan locations) are deduplicated

---

## cert-expiry-check.py

Alert-focused wrapper that scans the same paths as `cert-inventory.py` but **only reports certificates that are approaching expiry**. Certificates that are healthy are silently skipped. Designed for cron jobs and monitoring integrations.

### Syntax

```
python3 tools/certs/cert-expiry-check.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--days N` | From `[certs] warn_days` (default: 30) | Warning threshold in days. Certs expiring within N days are reported. |
| `--path PATH` | From `[certs] scan_paths` | Additional path to scan. Can be specified multiple times. |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Check with default 30-day threshold:**

```bash
python3 tools/certs/cert-expiry-check.py
```

**Use a 60-day warning threshold:**

```bash
python3 tools/certs/cert-expiry-check.py --days 60
```

**Add an extra scan path:**

```bash
python3 tools/certs/cert-expiry-check.py --path /opt/nginx/ssl
```

**JSON output:**

```bash
python3 tools/certs/cert-expiry-check.py --json
```

### Sample Output

**No issues found:**

```
==================================
  Certificate Expiry Check
==================================

  [OK]   All 6 certificate(s) expire in more than 30 days.
```

**Issues found:**

```
==================================
  Certificate Expiry Check
==================================

  File                Expires                    Days Left  Status
  ──────────────────  ─────────────────────────  ─────────  ──────
  webserver.crt       May  1 00:00:00 2026 GMT   20         WARN
  old-server.crt      Jan  1 00:00:00 2026 GMT   3          CRIT
```

### Exit Codes

This tool uses specific exit codes for integration with monitoring and automation:

| Exit Code | Meaning |
|-----------|---------|
| `0` | All certificates are healthy (none expiring within threshold) |
| `1` | One or more certificates are expiring within `critical_days` (CRITICAL) |
| `2` | One or more certificates are expiring within `warn_days` but not `critical_days` (WARNING) |

### Cron Integration

Run nightly and send output to a log file (or email via cron's MAILTO):

```bash
# /etc/cron.d/lrn-cert-check
MAILTO=admin@lrn.local
0 7 * * * root /usr/bin/python3 /home/mike/dev/lrn_tools/tools/certs/cert-expiry-check.py
```

Because non-zero exit codes trigger cron email output, you will automatically receive email when any certificate is within the warning or critical threshold.

### Nagios/Icinga Integration

The exit code contract matches Nagios plugin conventions:

```bash
# /etc/icinga2/conf.d/lrn-certs.conf (example)
object CheckCommand "lrn-cert-expiry" {
    command = [ "/usr/bin/python3",
                "/home/mike/dev/lrn_tools/tools/certs/cert-expiry-check.py" ]
}
```

### Difference Between the Two Cert Tools

| Feature | `cert-inventory.py` | `cert-expiry-check.py` |
|---------|--------------------|-----------------------|
| Purpose | Full audit / inventory | Alert-focused monitoring |
| Shows healthy certs | Yes | No |
| Exit code meaning | Always 0 on success | 0/2/1 = OK/WARN/CRIT |
| Best used for | Manual reviews, web dashboard | Cron, monitoring, scripting |
