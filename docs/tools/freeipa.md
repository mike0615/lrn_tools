# FreeIPA Tools

Tools for checking FreeIPA health, auditing users, and inventorying enrolled hosts.

| Tool | Script | Requires |
|------|--------|----------|
| IPA Health Check | `tools/freeipa/ipa-health-check.py` | `ipa`, `ipactl`, `openssl`, valid Kerberos TGT |
| User Report | `tools/freeipa/ipa-user-report.py` | `ipa` CLI, valid Kerberos TGT |
| Host Inventory | `tools/freeipa/ipa-host-inventory.py` | `ipa` CLI, valid Kerberos TGT |

### Prerequisites

All FreeIPA tools use the `ipa` CLI and must be run on a machine that:
1. Has `ipa-client` installed: `dnf install ipa-client`
2. Is enrolled in the IPA domain, or can reach the IPA server
3. Has a valid Kerberos TGT for a user with read access

**Obtain a TGT before running these tools:**

```bash
kinit admin
# or
kinit yourusername@LRN.LOCAL
```

Set `[ipa] server` in your config so tools know where to direct their queries.

---

## ipa-health-check.py

Comprehensive health check for a FreeIPA deployment. Checks four areas:

1. **Kerberos** — whether a valid TGT is present
2. **IPA Services** — runs `ipactl status` and checks each service state
3. **Replication** — queries replication agreements and their status
4. **CA Certificate** — checks the IPA CA cert expiry date

### Syntax

```
python3 tools/freeipa/ipa-health-check.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--server SERVER` | From `[ipa] server` | IPA server hostname to check (overrides config) |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Basic health check:**

```bash
python3 tools/freeipa/ipa-health-check.py
```

**Check a specific server:**

```bash
python3 tools/freeipa/ipa-health-check.py --server ipa02.lrn.local
```

**JSON output:**

```bash
python3 tools/freeipa/ipa-health-check.py --json | python3 -m json.tool
```

**Redirect to a file for later review:**

```bash
python3 tools/freeipa/ipa-health-check.py --json > /tmp/ipa-health-$(date +%Y%m%d).json
```

### Sample Output

```
=============================================
  FreeIPA Health Check
=============================================

--- Kerberos ---
  Check             Status  Detail
  ────────────────  ──────  ─────────────────────────────
  Kerberos TGT      OK      Valid TGT present

--- IPA Services (ipactl) ---
  Service                    State    Status
  ─────────────────────────  ───────  ──────
  Directory Service          running  OK
  krb5kdc Service            running  OK
  KPASSWD Service            running  OK
  HTTP Service               running  OK
  CA Service                 running  OK
  DNS Service                running  OK
  PKINIT Service             running  OK

--- Replication ---
  Replica          Role     Status
  ───────────────  ───────  ──────
  ipa01.lrn.local  master   OK
  ipa02.lrn.local  replica  OK

--- CA Certificate ---
  Cert    Subject              Expires                Days Left  Status
  ──────  ───────────────────  ─────────────────────  ─────────  ──────
  IPA CA  CN=Certificate Auth  Jan  1 00:00:00 2028   648        OK
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Service is running / cert is healthy / replication is active |
| `WARN` | No Kerberos TGT (IPA queries may fail); cert expiring soon |
| `FAIL` | Service is not running or replication agreement is broken |
| `CRIT` | CA certificate expiring within 7 days |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `2` | Warnings present (e.g., no TGT, cert approaching expiry) |
| `1` | Critical failures (service down, cert critically close to expiry) |

### Cron Usage

```bash
# Run daily and log output
0 6 * * * /usr/bin/python3 /home/mike/dev/lrn_tools/tools/freeipa/ipa-health-check.py \
    --json >> /var/log/lrn_tools/ipa-health.log 2>&1
```

---

## ipa-user-report.py

Lists all FreeIPA user accounts with their lock status, password expiry date, last login time, and email address. Useful for account audits, compliance reviews, and identifying stale accounts.

### Syntax

```
python3 tools/freeipa/ipa-user-report.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--locked` | off | Show **only** locked/disabled accounts |
| `--expiring` | off | Show **only** accounts with passwords expiring within 30 days _(filter applied to output; check Pwd Expires column)_ |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Full user report:**

```bash
python3 tools/freeipa/ipa-user-report.py
```

**Show only locked accounts:**

```bash
python3 tools/freeipa/ipa-user-report.py --locked
```

**JSON output for all users:**

```bash
python3 tools/freeipa/ipa-user-report.py --json
```

**Export to CSV via JSON:**

```bash
python3 tools/freeipa/ipa-user-report.py --json | \
    python3 -c "
import json, sys, csv
data = json.load(sys.stdin)
w = csv.DictWriter(sys.stdout, fieldnames=data['records'][0].keys())
w.writeheader(); w.writerows(data['records'])
"
```

### Sample Output

```
==================================
  FreeIPA User Report
==================================

  Total users: 24   Locked: 2

  UID          Full Name          Email                  Locked  Pwd Expires           Status
  ───────────  ─────────────────  ─────────────────────  ──────  ────────────────────  ──────
  admin        FreeIPA Admin      admin@lrn.local        no      never                 OK
  jsmith       John Smith         jsmith@lrn.local       no      2026-09-15 00:00:00   OK
  bjones       Bob Jones          bjones@lrn.local       YES     2025-12-01 00:00:00   WARN
  svcaccount   Service Account    svc@lrn.local          YES     never                 WARN
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Account is active and not locked |
| `WARN` | Account is locked or disabled |

### Notes

- The `ipa user-find` command is called with `--all --sizelimit=0` to retrieve all users and all attributes. On large directories this may take a few seconds.
- Password expiry dates are read from the `Kerberos password expiration` attribute. If your IPA policy does not set password expiry, this field will show `never`.
- Last login time is read from the `Last successful authentication` attribute. This requires the IPA `lastbind` plugin to be enabled.

---

## ipa-host-inventory.py

Enumerates all hosts enrolled in FreeIPA and reports their hostname, IP address, operating system, OS version, Kerberos principal, and whether an SSH public key is registered.

### Syntax

```
python3 tools/freeipa/ipa-host-inventory.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Basic host inventory:**

```bash
python3 tools/freeipa/ipa-host-inventory.py
```

**JSON output:**

```bash
python3 tools/freeipa/ipa-host-inventory.py --json
```

**Count enrolled hosts:**

```bash
python3 tools/freeipa/ipa-host-inventory.py --json | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['records']), 'enrolled hosts')"
```

**Filter to hosts with SSH keys registered:**

```bash
python3 tools/freeipa/ipa-host-inventory.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r['SSH Key'] == 'yes':
        print(r['Hostname'])
"
```

### Sample Output

```
===================================
  FreeIPA Host Inventory
===================================

  Enrolled hosts: 8

  Hostname               IP             OS           OS Ver   SSH Key  Status
  ─────────────────────  ─────────────  ───────────  ───────  ───────  ──────
  ipa01.lrn.local        192.168.1.11   Rocky Linux  9.7      yes      OK
  ipa02.lrn.local        192.168.1.12   Rocky Linux  9.7      yes      OK
  ns1.lrn.local          192.168.1.10   Rocky Linux  9.7      yes      OK
  webserver.lrn.local    192.168.1.20   Rocky Linux  9.7      yes      OK
  devbox.lrn.local       192.168.1.50   Rocky Linux  10.0     no       OK
```

### Using as Ansible Inventory Source

The JSON output can feed an Ansible dynamic inventory script:

```bash
python3 tools/freeipa/ipa-host-inventory.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
print('[all]')
for r in d['records']:
    if r['Hostname']:
        print(r['Hostname'])
" > /tmp/ipa_inventory.ini
```

### Notes

- The `IP` field is populated from the IPA host object's managed-by or IP address attribute. Hosts enrolled without a registered IP will show an empty value.
- OS and OS version fields are only populated if they were set during enrollment (`ipa host-mod --os "Rocky Linux" --osversion 9.7 hostname`).
- If `ipa host-find` returns no results but IPA is accessible, ensure the logged-in user has read access to host objects.
