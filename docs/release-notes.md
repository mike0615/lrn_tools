# LRN Tools — Release Notes

All notable changes to this project are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-04-11

### Added

#### `tools/dns/gen-reverse-zones.py` — Initial Release

First tool in the LRN Tools collection. Automates the generation of BIND 9 reverse lookup zones from an existing forward lookup zone file.

**Features:**
- Parses `$ORIGIN`, `$TTL`, SOA, NS, A, and AAAA records from a BIND 9 zone file
- Handles multi-line parenthesised SOA blocks
- Resolves relative and `@` hostnames to FQDNs using `$ORIGIN`
- Groups IPv4 `A` records by `/24` subnet, producing one reverse zone file per block
- Groups IPv6 `AAAA` records by `/64` prefix (nibble notation)
- Inherits SOA timers (refresh, retry, expire, minimum) from the forward zone
- Auto-generates a `YYYYMMDDnn`-format serial number
- Sorts PTR records by last octet for readability
- `--dry-run` mode prints output to stdout without touching the filesystem
- `--print-conf` emits ready-to-paste `named.conf` zone stanza(s)
- CLI flags to override nameserver, hostmaster email, and TTL
- `--no-ipv6` flag to skip AAAA processing
- Zero external dependencies — Python 3.6+ standard library only

---

---

## [2.0.0] — 2026-04-11

### Added — Full Admin Toolkit

Complete administration suite across 9 tool categories, plus a TUI console and web dashboard.

#### Core Framework
- `lib/common.py` — Shared library: ANSI color output, `run_cmd()`, ASCII table formatter, `ToolOutput` JSON schema, `make_base_parser()`. All tools import this.
- `lib/config.py` — INI config loader with typed accessors and sensible defaults. Site config lives at `~/.lrn_tools/config.ini`.
- `lib/registry.py` — Single source of truth for all tools. Both TUI and web auto-discover tools from here.
- `install.sh` — Idempotent installer: scaffolds config, creates symlinks (`lrn-admin`, `lrn-web`), optionally installs a systemd unit.

#### TUI (`tui/lrn_admin.py`)
Two-pane ncurses console. Left pane: categories. Right pane: tools. Bottom: live streaming output. Navigate with arrow keys; run tools with Enter or `a` for custom args.

#### Web Dashboard (`web/`)
Flask application with zero CDN dependencies. Runs on `127.0.0.1:5000` by default. Features: tool browser, live SSE output streaming, structured JSON report rendering with status badges, dark theme.

#### DNS Tools (`tools/dns/`)
- `dns-query-test.py` — Forward/reverse/SRV/MX queries across multiple DNS servers; flags cross-server disagreements
- `zone-consistency-check.py` — For every A record in a zone file, queries the PTR and reports mismatches

#### FreeIPA Tools (`tools/freeipa/`)
- `ipa-health-check.py` — ipactl status, replication agreements, CA cert expiry, Kerberos TGT check
- `ipa-user-report.py` — All users with lock status, password expiry; filter to locked or expiring accounts
- `ipa-host-inventory.py` — Enrolled hosts with OS, IP, SSH key status

#### Certificate Tools (`tools/certs/`)
- `cert-inventory.py` — Scans configured paths for PEM certs; reports CN, SAN, issuer, days to expiry
- `cert-expiry-check.py` — Alert-focused expiry checker; exit code 0/2/1 maps to OK/WARN/CRIT for use in cron/monitoring

#### System Tools (`tools/system/`)
- `sysinfo.py` — OS, kernel, CPU, RAM, disk, uptime, SELinux mode, FIPS status, NTP sync
- `service-status.py` — Checks configured critical services; `--all-failed` shows all failed units system-wide
- `troubleshoot.py` — Automated triage covering DNS resolution, time sync, IPA connectivity, Kerberos TGT, SELinux, disk space

#### KVM Tools (`tools/kvm/`)
- `vm-list.py` — All VMs with state, vCPU, RAM, disk, autostart, network interfaces
- `vm-snapshot-report.py` — Snapshot inventory per VM; flags snapshots older than configured threshold

#### DNF Tools (`tools/dnf/`)
- `repo-health.py` — Enabled repos with TCP reachability test per baseurl
- `updates-available.py` — Available updates with security advisory cross-reference and severity grouping

#### Docker Tools (`tools/docker/`)
- `container-status.py` — All containers with image, state, ports; plus image inventory
- `compose-health.py` — Scans configured compose project directories and checks service states

#### Network Tools (`tools/network/`)
- `connectivity-check.py` — ICMP ping and TCP connect sweep with latency and packet loss
- `port-scan.py` — TCP reachability check for configured service endpoints; `--local` shows listening ports via `ss`

#### Log Tools (`tools/logs/`)
- `journal-errors.py` — Queries journald for ERROR/CRITICAL entries grouped by systemd unit with counts
- `log-summary.py` — Scans configured log files with configurable regex patterns; frequency table sorted by count

---

## Upcoming / Planned

| Tool | Category | Description |
|------|----------|-------------|
| `ipa-user-import.py` | FreeIPA | Bulk import users into FreeIPA from CSV |
| `named-conf-audit.py` | DNS | Audit named.conf for common misconfigurations |
| `ansible-inv-from-ipa.py` | Automation | Generate Ansible inventory from FreeIPA host records |
| `net-arp-report.py` | Network | ARP table dump and stale entry analysis |
| `log-auth-report.py` | Logs | Detailed failed login and sudo usage report from /var/log/secure |
