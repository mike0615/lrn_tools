# Network Tools

Tools for testing host reachability and verifying TCP service endpoints in the LRN environment.

| Tool | Script | Requires |
|------|--------|----------|
| Connectivity Check | `tools/network/connectivity-check.py` | `ping` (system), `socket` (stdlib) |
| Port Check | `tools/network/port-scan.py` | `socket` (stdlib), `ss` (system) |

---

## connectivity-check.py

Performs ICMP ping and TCP connection tests against a configured list of hosts and services. Reports latency, packet loss, and overall reachability status for each target.

### Syntax

```
python3 tools/network/connectivity-check.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--host TARGET` | From `[network] check_hosts` | Additional host to check. Format: `host:port:label` (TCP), `host:icmp:label` (ICMP), or just `host` (ICMP). Can be specified multiple times. |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Target Format

| Format | Protocol | Example |
|--------|----------|---------|
| `host` | ICMP ping | `192.168.1.1` |
| `host:icmp:label` | ICMP ping | `192.168.1.1:icmp:gateway` |
| `host:PORT:label` | TCP connect | `ipa01.lrn.local:443:ipa-https` |
| `hostname:53:dns` | TCP connect to port 53 | `192.168.1.10:53:dns-primary` |

### Examples

**Check all configured hosts:**

```bash
python3 tools/network/connectivity-check.py
```

**Add extra hosts on the command line:**

```bash
python3 tools/network/connectivity-check.py \
    --host 192.168.1.50:icmp:new-server \
    --host 192.168.1.50:22:new-server-ssh
```

**JSON output:**

```bash
python3 tools/network/connectivity-check.py --json
```

**Show only failures:**

```bash
python3 tools/network/connectivity-check.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r['Status'] == 'FAIL':
        print('[FAIL]', r['Label'], ':', r['Host'])
"
```

**Quick check of a single host:**

```bash
python3 tools/network/connectivity-check.py --host 192.168.1.200:icmp:test
```

### Sample Output

```
=====================================
  Connectivity Check
=====================================

  Label           Host              Protocol  Port  Latency    Loss%  Status
  ──────────────  ────────────────  ────────  ────  ─────────  ─────  ──────
  gateway         192.168.1.1       ICMP      -     0.8 ms     0%     OK
  dns-primary     192.168.1.10      TCP       53    1.2 ms     -      OK
  ipa-https       192.168.1.10      TCP       443   2.1 ms     -      OK
  dns-secondary   192.168.1.11      TCP       53    1.5 ms     -      OK
  old-monitoring  192.168.1.99      ICMP      -     -          100%   FAIL
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Host is reachable with 0% packet loss (ICMP) or TCP connect succeeded |
| `WARN` | Host is partially reachable (ICMP only: 1-49% packet loss) |
| `FAIL` | Host is unreachable (100% packet loss or TCP connect failed) |

### ICMP vs TCP

- **ICMP (`ping`)**: Tests basic network reachability. Can be blocked by firewalls even when the host is up and services are running. A FAIL here may just mean ICMP is filtered.
- **TCP connect**: Tests whether a specific service port is open and accepting connections. More reliable than ICMP for service health verification.

Use TCP checks for service-level validation and ICMP checks for gateway/infrastructure reachability.

### Config Example

```ini
[network]
check_hosts =
    192.168.1.1:icmp:gateway,
    192.168.1.10:53:dns-primary,
    192.168.1.10:443:ipa-https,
    192.168.1.10:389:ipa-ldap,
    192.168.1.11:53:dns-secondary,
    192.168.1.20:icmp:webserver,
    192.168.1.20:443:webserver-https
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All targets are reachable |
| `2` | One or more targets have degraded connectivity (WARN) |
| `1` | One or more targets are unreachable (FAIL) |

### Cron Usage

```bash
# Check every 5 minutes and log results
*/5 * * * * /usr/bin/python3 /home/mike/dev/lrn_tools/tools/network/connectivity-check.py \
    --json >> /var/log/lrn_tools/connectivity.log 2>&1
```

---

## port-scan.py

Verifies TCP reachability of configured service endpoints. Distinct from `connectivity-check.py` in that it is service-oriented — focused on checking specific host:port combinations that represent services you care about. Also includes a `--local` mode that shows all locally listening ports.

### Syntax

```
python3 tools/network/port-scan.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--target HOST:PORT[:DESC]` | From `[network] port_checks` | TCP target to check. Can be specified multiple times. |
| `--local` | off | Also show locally listening TCP ports (uses `ss -tlnp`) |
| `--timeout N` | `3` | TCP connect timeout in seconds per target |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Check all configured port targets:**

```bash
python3 tools/network/port-scan.py
```

**Add an extra target:**

```bash
python3 tools/network/port-scan.py --target 192.168.1.50:8443:myapp-https
```

**Show local listening ports:**

```bash
python3 tools/network/port-scan.py --local
```

**Show local listening ports only (no remote checks):**

```bash
python3 tools/network/port-scan.py --local --target dummy:99:skip 2>/dev/null || \
python3 tools/network/port-scan.py --local
```

**Use a longer timeout for slow services:**

```bash
python3 tools/network/port-scan.py --timeout 10
```

**JSON output:**

```bash
python3 tools/network/port-scan.py --json
```

**Find closed ports among configured checks:**

```bash
python3 tools/network/port-scan.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
closed = [r for r in d['records'] if r.get('State') != 'OPEN']
if not closed:
    print('All ports are open.')
else:
    for r in closed:
        print(f\"[{r['State']}] {r['Host']}:{r['Port']} ({r['Service']})\")
"
```

### Sample Output

**Remote port checks:**

```
=================================
  Port Check
=================================

--- Remote Port Checks ---
  Host              Port  Service    State    Latency  Status
  ────────────────  ────  ─────────  ───────  ───────  ──────
  ipa01.lrn.local   389   ldap       OPEN     1.4 ms   OK
  ipa01.lrn.local   636   ldaps      OPEN     1.6 ms   OK
  ipa01.lrn.local   88    kerberos   OPEN     0.9 ms   OK
  ipa01.lrn.local   443   ipa-https  OPEN     2.3 ms   OK
  192.168.1.10      53    dns-tcp    OPEN     0.5 ms   OK
```

**With `--local`:**

```
--- Local Listening Ports ---
  Local Address      Port  Service       Process
  ─────────────────  ────  ────────────  ─────────────────────────────
  0.0.0.0:22         22    SSH           sshd,pid=1234
  0.0.0.0:53         53    DNS           named,pid=5678
  0.0.0.0:389        389   LDAP          ns-slapd,pid=9012
  0.0.0.0:636        636   LDAPS         ns-slapd,pid=9012
  127.0.0.1:953      953                 named,pid=5678
```

### TCP State Values

| State | Meaning |
|-------|---------|
| `OPEN` | TCP three-way handshake completed — service is accepting connections |
| `REFUSED` | TCP RST received — host is up but nothing is listening on this port |
| `TIMEOUT` | No response within the timeout — host may be down or port is firewalled |
| `ERROR` | Unexpected socket error (e.g., network unreachable) |

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Port is open |
| `WARN` | Connection timed out |
| `FAIL` | Connection refused or error |

### Well-Known Port Reference

The tool automatically maps port numbers to service names for common ports:

| Port | Service |
|------|---------|
| 22 | SSH |
| 53 | DNS |
| 80 | HTTP |
| 88 | Kerberos |
| 389 | LDAP |
| 443 | HTTPS |
| 464 | kpasswd |
| 636 | LDAPS |
| 3306 | MySQL |
| 5432 | PostgreSQL |
| 8080 | HTTP-Alt |
| 8443 | HTTPS-Alt |
| 9200 | Elasticsearch |

### Config Example

```ini
[network]
port_checks =
    ipa01.lrn.local:389:ldap,
    ipa01.lrn.local:636:ldaps,
    ipa01.lrn.local:88:kerberos,
    ipa01.lrn.local:443:ipa-https,
    ns1.lrn.local:53:dns-primary,
    webserver.lrn.local:443:web-https,
    monitoring.lrn.local:3000:grafana,
    monitoring.lrn.local:9200:elasticsearch
```

### Difference Between connectivity-check and port-scan

| Feature | `connectivity-check.py` | `port-scan.py` |
|---------|------------------------|----------------|
| ICMP ping | Yes | No |
| TCP connect | Yes | Yes |
| Latency + packet loss | Yes (ICMP) | Latency only (TCP) |
| Local port listing | No | Yes (`--local`) |
| Best for | Network path reachability | Service endpoint verification |

Use both together for comprehensive network health validation.
