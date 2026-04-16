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

---

## [2.1.0] — 2026-04-16

### Added — LRN Man Mascot & UI Theming

#### LRN Man (`web/static/img/lrn-man.png`)
- Superhero mascot character with floating speech bubble on every web page
- 200+ contextual tips organized by tool category (dns, freeipa, certs, system, kvm, dnf, docker, network, logs)
- Result-aware commentary: different quips for exit code 0 (success), 1 (error), 2 (warning)
- Mascot can be toggled on/off; state persists in `localStorage`

#### Light / Dark Mode
- Full light theme (GitHub-style palette) alongside the existing dark theme
- Toggle button in the top bar; preference persists in `localStorage`
- CSS custom properties architecture — all colors defined under `:root` / `[data-theme]`

### Changed
- Top bar now includes theme toggle (☀/🌙) and mascot toggle (🛡 Guide: ON/OFF) controls

---

## [2.2.0] — 2026-04-16

### Added — Remote Host Execution

#### Remote Host Management (`lib/hosts.py`, `web/templates/hosts.html`, `web/templates/host_form.html`)
- Save SSH host profiles: name, host/IP, port, user, auth type, key path or password, lrn_path, notes
- Profiles stored in `~/.lrn_tools/hosts.json` (chmod 600; password field never sent to templates)
- **Test** button per host: verifies SSH connectivity and confirms lrn_tools is present at the configured path
- **Edit** and **Delete** actions per host

#### Run Tools Remotely
- Every tool run page now includes a host selector (Local + all saved hosts)
- Blocking `/run/<tool_id>` and streaming `/stream/<tool_id>` both accept a `host_id` parameter
- Remote execution uses `python3 -u` (unbuffered) over SSH for correct SSE streaming
- Key auth: system `ssh` binary with `BatchMode=yes`; password auth: `sshpass` wrapper

#### API
- `GET /api/hosts` — JSON list of saved host profiles (sanitized, no password field)

---

## [2.3.0] — 2026-04-16

### Added — 6 New Tools, /opt Install Path & One-Click Deploy

#### New Tools

- **`tools/network/subnet-calc.py`** (`net-subnet-calc`) — IPv4/IPv6 subnet analyser
  - Network address, prefix length, netmask, wildcard mask, broadcast, first/last host, usable host count
  - `--split PREFIX` — subdivide a network into subnets of a smaller prefix (capped at 512)
  - `--list-subnets PREFIX` — list all subnets after a split
  - Zero external dependencies; uses Python `ipaddress` stdlib

- **`tools/system/ssh-keygen-tool.py`** (`sys-ssh-keygen`) — SSH key pair generator
  - Generates ed25519, rsa, ecdsa, or dsa keys via the system `ssh-keygen`
  - `--list` — inventories existing keys in the target directory
  - Prints public key content and ready-to-paste `ssh-copy-id` commands

- **`tools/system/password-hash.py`** (`sys-password-hash`) — Multi-format password hasher
  - Formats: SHA-512crypt (`-6`), SHA-256crypt (`-5`), MD5crypt (`-1`), htpasswd APR1, SHA-256/512/1/MD5 hex digests
  - `--format` selects algorithm; `--all` outputs every format at once
  - Interactive `getpass` prompt when `--password` is omitted (no plaintext in shell history)

- **`tools/logs/audit-log.py`** (`log-audit`) — Linux audit log collector and viewer
  - Primary: `ausearch --interpret` for structured event parsing
  - Fallback: direct regex parse of `/var/log/audit/audit.log`
  - `aureport` summary mode (`--summary`): authentication, modifications, executables, AVC events
  - Filter by hours (`--hours`), event type (`--type`), and username (`--user`)
  - Exit 2 when any failure-result events are found

- **`tools/system/software-inventory.py`** (`sys-software-inventory`) — RPM package inventory
  - Queries `rpm -qa` with install timestamp, name, version, arch, vendor, repo, size
  - `--recent DAYS` — show only packages installed in the last N days
  - `--search TERM` — filter by name substring
  - `--vendor` / `--repo` — filter by vendor or repository
  - Sort by date (default), name, or size

- **`tools/system/status-report.py`** (`sys-status-report`) — Comprehensive system status report
  - Sections: Identity (OS, uptime, load, FIPS, SELinux), Memory, Disk, Critical Services, Network, Time Sync, Journal Errors, Recent Logins
  - Per-section thresholds (e.g. 80%/90% disk, 75%/90% RAM) with WARN/ERROR/OK status
  - Overall exit code: 0=OK, 1=ERROR, 2=WARN — suitable for monitoring/cron

#### Install Path — /opt Default
- `install.sh` now defaults to `/opt/lrn_tools` when run as root; `~/dev/lrn_tools` for non-root
- Override with `LRN_INSTALL_PATH=/custom/path sudo bash install.sh`
- If source ≠ install path, rsyncs the repo to the target and chowns to `SUDO_USER`
- Systemd unit `WorkingDirectory` set to install path automatically

#### One-Click Remote Deploy (`lib/hosts.py` — `deploy_lrn_tools()`)
- **Deploy** button on the Remote Hosts page streams a live rsync transfer to any saved host
- Uses `rsync -avz --delete --progress` with excludes for `.git`, `__pycache__`, `*.pyc`, `hosts.json`
- sshpass wrapper applied automatically for password-auth hosts
- On success, prints the `install.sh` command to run on the remote host

---

## Upcoming / Planned

| Tool | Category | Description |
|------|----------|-------------|
| `ipa-user-import.py` | FreeIPA | Bulk import users into FreeIPA from CSV |
| `named-conf-audit.py` | DNS | Audit named.conf for common misconfigurations |
| `ansible-inv-from-ipa.py` | Automation | Generate Ansible inventory from FreeIPA host records |
| `net-arp-report.py` | Network | ARP table dump and stale entry analysis |
| `log-auth-report.py` | Logs | Detailed failed login and sudo usage report from /var/log/secure |
| WSGI production server | Web | Replace Flask dev server with gunicorn or waitress |
| `backup-status.py` | System | Report on backup job history from common backup tools |
| `firewall-report.py` | Network | Summarise active firewalld zones, rules, and open ports |
