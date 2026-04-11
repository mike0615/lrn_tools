# Configuration Reference

LRN Tools reads its configuration from `~/.lrn_tools/config.ini`.

The file uses standard INI format (`[section]` headers, `key = value` pairs).  
All keys are optional unless marked **REQUIRED**. Missing optional keys fall back to the documented defaults.

To create your initial config:

```bash
mkdir -p ~/.lrn_tools
cp ~/dev/lrn_tools/config/lrn_tools.conf.example ~/.lrn_tools/config.ini
vi ~/.lrn_tools/config.ini
```

---

## [general]

General behaviour settings.

| Key | Default | Description |
|-----|---------|-------------|
| `site_name` | `LRN Lab` | Display name shown in the TUI header and web dashboard title bar |
| `default_format` | `table` | Default output format for interactive use: `table` or `json` |
| `tool_timeout` | `60` | Maximum seconds a tool is allowed to run before the web runner kills it |

```ini
[general]
site_name = LRN Lab
default_format = table
tool_timeout = 60
```

---

## [ipa]

Settings for FreeIPA tools. Used by `ipa-health-check.py`, `ipa-user-report.py`, and `ipa-host-inventory.py`.

| Key | Default | Description |
|-----|---------|-------------|
| `server` | _(empty)_ | **REQUIRED for IPA tools.** Hostname of your primary IPA server, e.g. `ipa01.lrn.local` |
| `realm` | _derived_ | Kerberos realm. If not set, derived from server hostname by uppercasing the domain component. `ipa01.lrn.local` → `LRN.LOCAL` |
| `admin_principal` | _(empty)_ | Kerberos principal for IPA CLI calls, e.g. `admin@LRN.LOCAL`. If not set, tools use the current user's ticket. |
| `keytab_path` | _(empty)_ | Path to a keytab for non-interactive Kerberos auth. Optional — if absent, the user must have a valid TGT. |

```ini
[ipa]
server = ipa01.lrn.local
realm = LRN.LOCAL
admin_principal = admin@LRN.LOCAL
# keytab_path = /etc/lrn_tools/admin.keytab
```

**Note:** IPA tools call the `ipa` CLI and `ipactl` commands. These must be installed (`dnf install ipa-client`) and the machine must be enrolled or able to reach the IPA server. A valid Kerberos TGT (`kinit admin`) is needed for most queries.

---

## [dns]

Settings for DNS tools.

| Key | Default | Description |
|-----|---------|-------------|
| `servers` | `127.0.0.1` | Space-separated list of DNS server IPs to query. Used by `dns-query-test.py` and `zone-consistency-check.py`. |
| `domain` | _(empty)_ | Default DNS domain for unqualified queries, e.g. `lrn.local`. Used to construct IPA SRV record names. |
| `named_conf` | `/etc/named.conf` | Path to the BIND named.conf file. Reserved for future `named-conf-audit.py`. |
| `zone_dir` | `/var/named` | Directory containing BIND zone files. |

```ini
[dns]
servers = 192.168.1.10 192.168.1.11
domain = lrn.local
named_conf = /etc/named.conf
zone_dir = /var/named
```

---

## [certs]

Settings for certificate tools.

| Key | Default | Description |
|-----|---------|-------------|
| `scan_paths` | `/etc/pki/tls/certs`<br>`/etc/ipa/ca.crt` | Newline or comma-separated list of files or directories to scan for PEM certificates. Directories are searched recursively for `*.pem`, `*.crt`, `*.cer` files. |
| `warn_days` | `30` | Certificates expiring within this many days are flagged as WARN. |
| `critical_days` | `7` | Certificates expiring within this many days are flagged as CRIT. |
| `ipa_nssdb` | _(empty)_ | Path to the IPA NSSDB directory, e.g. `/etc/dirsrv/slapd-LRN-LOCAL`. Reserved for future NSSDB-aware cert scanning. |

```ini
[certs]
scan_paths =
    /etc/pki/tls/certs
    /etc/ipa/ca.crt
    /etc/pki/ca-trust/source/anchors
warn_days = 30
critical_days = 7
```

---

## [services]

Settings for `service-status.py`.

| Key | Default | Description |
|-----|---------|-------------|
| `critical_services` | `named,chronyd` | Newline or comma-separated list of systemd unit names to check. Include the full unit name as it appears in `systemctl status`. |

```ini
[services]
critical_services =
    named,
    dirsrv@LRN-LOCAL,
    krb5kdc,
    httpd,
    ipa,
    chronyd,
    firewalld,
    sshd
```

**Note:** Use the exact unit name shown by `systemctl list-units`. For parameterized units like `dirsrv@LRN-LOCAL`, include the full instance name.

---

## [kvm]

Settings for KVM tools.

| Key | Default | Description |
|-----|---------|-------------|
| `libvirt_uri` | `qemu:///system` | Libvirt connection URI. Use `qemu:///system` for the local system hypervisor. For remote: `qemu+ssh://root@host/system`. |
| `snapshot_stale_days` | `14` | Snapshots older than this many days are flagged as stale by `vm-snapshot-report.py`. |

```ini
[kvm]
libvirt_uri = qemu:///system
snapshot_stale_days = 14
```

---

## [docker]

Settings for Docker Compose tools.

| Key | Default | Description |
|-----|---------|-------------|
| `compose_paths` | _(empty)_ | Newline or comma-separated list of directories to search for `docker-compose.yml` / `compose.yml` files. Each directory should be the root of a compose project. |

```ini
[docker]
compose_paths =
    /opt/compose/monitoring,
    /opt/compose/registry,
    /opt/compose/gitlab
```

---

## [network]

Settings for network tools.

| Key | Default | Description |
|-----|---------|-------------|
| `check_hosts` | _(empty)_ | Newline or comma-separated list of connectivity check targets. Format: `host:port:label` for TCP, `host:icmp:label` for ICMP ping, or just `host` for ICMP. |
| `port_checks` | _(empty)_ | Newline or comma-separated list of TCP port checks. Format: `host:port:description`. |

```ini
[network]
check_hosts =
    192.168.1.1:icmp:gateway,
    192.168.1.10:53:dns-primary,
    192.168.1.10:443:ipa-https,
    192.168.1.11:53:dns-secondary,
    192.168.1.20:icmp:monitoring

port_checks =
    ipa01.lrn.local:389:ldap,
    ipa01.lrn.local:636:ldaps,
    ipa01.lrn.local:88:kerberos,
    ipa01.lrn.local:443:ipa-https,
    192.168.1.10:53:dns-tcp
```

**Target format detail:**

| Format | Proto | Example |
|--------|-------|---------|
| `host` | ICMP ping | `192.168.1.1` |
| `host:icmp:label` | ICMP ping | `192.168.1.1:icmp:gateway` |
| `host:PORT:label` | TCP connect | `ipa01.lrn.local:443:ipa-https` |

---

## [logs]

Settings for log analysis tools.

| Key | Default | Description |
|-----|---------|-------------|
| `watch_files` | `/var/log/messages` | Newline or comma-separated list of log files to scan with `log-summary.py`. |
| `patterns` | _(empty)_ | Custom regex patterns in `name=regex` format, one per line. Added on top of the built-in default patterns. |

```ini
[logs]
watch_files =
    /var/log/messages,
    /var/log/secure,
    /var/log/named/query.log,
    /var/log/dirsrv/slapd-LRN-LOCAL/access

patterns =
    custom_app_error=MY_APP_EXCEPTION
    ipa_op_failed=Failed to .* for user
```

**Built-in patterns** (always active, cannot be disabled):

| Name | Pattern |
|------|---------|
| ERROR | `\bERROR\b` |
| WARNING | `\bWARN(ING)?\b` |
| CRITICAL | `\bCRITICAL\b` |
| Auth Failure | `authentication failure\|Failed password\|Invalid user` |
| Denied | `\bDENIED\b` |
| Segfault | `\bsegfault\b` |

---

## [web]

Settings for the web dashboard.

| Key | Default | Description |
|-----|---------|-------------|
| `host` | `127.0.0.1` | IP address to bind the Flask server to. Use `0.0.0.0` to listen on all interfaces. |
| `port` | `5000` | TCP port for the web dashboard. |
| `secret_key` | `change-me-in-production` | Flask session secret key. **Change this** to a random string in any non-dev deployment. Generate one with: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `debug` | `false` | Enable Flask debug mode. **Never set to `true` in production** — exposes a debugger. |

```ini
[web]
host = 127.0.0.1
port = 5000
secret_key = your-long-random-secret-here
debug = false
```

---

## [tui]

Settings for the TUI console.

| Key | Default | Description |
|-----|---------|-------------|
| `color_scheme` | `default` | Color scheme for the TUI. Currently `default` is the only option; future versions may add `light`. |

```ini
[tui]
color_scheme = default
```

---

## Multi-line Values

Any value can span multiple lines by indenting continuation lines:

```ini
[services]
critical_services =
    named,
    chronyd,
    sshd
```

Or use commas on a single line:

```ini
[services]
critical_services = named, chronyd, sshd
```

Both styles work. The config loader strips whitespace and splits on both newlines and commas.

---

## Using Multiple Configs

Any tool accepts `--config PATH` to override the default location:

```bash
python3 tools/system/sysinfo.py --config /etc/lrn_tools/prod.ini
python3 tools/system/sysinfo.py --config ~/lrn_tools_dev.ini
```

This is useful for managing multiple environments (e.g., prod IPA vs. lab IPA) from the same workstation.
