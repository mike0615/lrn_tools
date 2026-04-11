# LRN Tools

A comprehensive suite of CLI administration tools for the **Local Restricted Network (LRN)** — an air-gapped, enterprise-grade lab environment running Rocky Linux 9/10, FreeIPA, BIND 9, KVM, and related infrastructure.

All tools are designed to be:
- **Air-gap friendly** — standard library only at runtime (except Flask for the web dashboard)
- **Dual-mode** — human-readable terminal output by default; `--json` for machine consumption
- **Standalone** — every tool runs directly from the CLI, independent of the TUI or web dashboard
- **Production-ready** — structured output, proper exit codes, real error handling

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/mike0615/lrn_tools.git
cd lrn_tools
bash install.sh

# Edit your site config
vi ~/.lrn_tools/config.ini

# Launch the TUI console
lrn-admin

# Or start the web dashboard
lrn-web
# Open http://127.0.0.1:5000
```

---

## Interfaces

### Text-based TUI (`lrn-admin`)

A two-pane ncurses console. Left pane shows tool categories, right pane shows tools in the selected category. Press Enter to run a tool; output streams live into the bottom panel.

```
lrn-admin
```

Key bindings: `Tab` switch pane · `Enter` run tool · `a` run with args · `PgUp/PgDn` scroll · `?` help · `q` quit

### Web Dashboard (`lrn-web`)

Flask-based web UI with zero CDN dependencies (fully air-gap safe). Runs any tool from the browser, streams output live, and renders structured JSON reports as sortable tables.

```bash
lrn-web                        # starts on 127.0.0.1:5000
lrn-web --host 0.0.0.0        # listen on all interfaces
```

Install Flask if needed: `dnf install python3-flask`

---

## Tool Categories

### DNS (`tools/dns/`)

| Tool | Description |
|------|-------------|
| `gen-reverse-zones.py` | Generate BIND 9 reverse zones from a forward zone file |
| `dns-query-test.py` | Test forward/reverse/SRV queries against configured DNS servers |
| `zone-consistency-check.py` | Cross-validate A records against PTR records in live DNS |

### FreeIPA (`tools/freeipa/`)

| Tool | Description |
|------|-------------|
| `ipa-health-check.py` | Check IPA services, replication agreements, CA cert expiry |
| `ipa-user-report.py` | List users with lock status, password expiry, and groups |
| `ipa-host-inventory.py` | Enumerate enrolled hosts with OS, IP, and enrollment info |

### Certificates (`tools/certs/`)

| Tool | Description |
|------|-------------|
| `cert-inventory.py` | Scan configured paths for PEM certs — subject, SAN, expiry |
| `cert-expiry-check.py` | Alert on certs expiring within threshold (exit 0/2/1 = OK/WARN/CRIT) |

### System (`tools/system/`)

| Tool | Description |
|------|-------------|
| `sysinfo.py` | OS, kernel, CPU, RAM, disk, uptime, SELinux, FIPS, NTP |
| `service-status.py` | Check configured critical systemd services |
| `troubleshoot.py` | Automated triage: DNS, time sync, connectivity, Kerberos |

### KVM (`tools/kvm/`)

| Tool | Description |
|------|-------------|
| `vm-list.py` | List all VMs with state, vCPU, RAM, autostart, interfaces |
| `vm-snapshot-report.py` | List snapshots and flag stale ones older than threshold |

### DNF (`tools/dnf/`)

| Tool | Description |
|------|-------------|
| `repo-health.py` | Check enabled repos and test their network reachability |
| `updates-available.py` | List available updates grouped by security/bugfix/enhancement |

### Docker (`tools/docker/`)

| Tool | Description |
|------|-------------|
| `container-status.py` | List containers with image, state, ports, and restart info |
| `compose-health.py` | Check Docker Compose service health across configured projects |

### Network (`tools/network/`)

| Tool | Description |
|------|-------------|
| `connectivity-check.py` | ICMP/TCP sweep of configured hosts with latency reporting |
| `port-scan.py` | Verify TCP reachability of service endpoints; show local listening ports |

### Logs (`tools/logs/`)

| Tool | Description |
|------|-------------|
| `journal-errors.py` | Query journald for ERROR/CRITICAL entries grouped by unit |
| `log-summary.py` | Scan log files with regex patterns and report match frequency |

---

## Repository Layout

```
lrn_tools/
├── install.sh                  # System installer — creates config, symlinks, optional systemd unit
├── config/
│   └── lrn_tools.conf.example  # Starter config — copy to ~/.lrn_tools/config.ini
├── lib/
│   ├── common.py               # Shared: colors, run_cmd, tables, JSON schema, base argparse
│   ├── config.py               # Config file loader with typed accessors
│   └── registry.py             # Tool registry — single source of truth for TUI and web
├── tui/
│   └── lrn_admin.py            # ncurses two-pane TUI launcher
├── web/
│   ├── app.py                  # Flask web dashboard
│   ├── templates/              # Jinja2 HTML templates (no CDN)
│   └── static/                 # CSS and vanilla JS (fully self-contained)
├── tools/
│   ├── dns/
│   ├── freeipa/
│   ├── certs/
│   ├── system/
│   ├── kvm/
│   ├── dnf/
│   ├── docker/
│   ├── network/
│   └── logs/
└── docs/
    ├── how-to-use.md
    └── release-notes.md
```

---

## Adding New Tools

1. Drop your script into `tools/<category>/your-tool.py`
2. Follow the pattern: `make_base_parser()` → `emit_json()` → `print_table()`
3. Add an entry to `lib/registry.py` — the TUI and web dashboard auto-discover it
4. Update the table above and add a section to `docs/how-to-use.md`
5. Add a `docs/release-notes.md` entry

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.6+ (standard library only for all CLI tools) |
| Flask | `dnf install python3-flask` (web dashboard only) |
| BIND utils | `dnf install bind-utils` (for `dns-query-test.py`) |
| libvirt-client | `dnf install libvirt-client` (for KVM tools) |
| Docker | `dnf install docker-ce` or `podman-docker` (for Docker tools) |

---

## License

MIT
