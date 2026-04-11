# LRN Tools — Documentation Index

Full usage reference for all tools, interfaces, and configuration.

---

## Contents

| Document | Description |
|----------|-------------|
| [Installation & Setup](install.md) | System requirements, install script, config scaffold |
| [Configuration Reference](config-reference.md) | All `config.ini` settings explained |
| [TUI Console](tui.md) | `lrn-admin` text-based menu — keys, layout, usage |
| [Web Dashboard](web.md) | `lrn-web` Flask dashboard — startup, features, streaming |
| **Tool Categories** | |
| [DNS Tools](tools/dns.md) | gen-reverse-zones, dns-query-test, zone-consistency-check |
| [FreeIPA Tools](tools/freeipa.md) | ipa-health-check, ipa-user-report, ipa-host-inventory |
| [Certificate Tools](tools/certs.md) | cert-inventory, cert-expiry-check |
| [System Tools](tools/system.md) | sysinfo, service-status, troubleshoot |
| [KVM Tools](tools/kvm.md) | vm-list, vm-snapshot-report |
| [DNF Tools](tools/dnf.md) | repo-health, updates-available |
| [Docker Tools](tools/docker.md) | container-status, compose-health |
| [Network Tools](tools/network.md) | connectivity-check, port-scan |
| [Log Tools](tools/logs.md) | journal-errors, log-summary |

---

## Quick Reference — All Tool Options

| Tool | Path | Key Flags |
|------|------|-----------|
| `gen-reverse-zones` | `tools/dns/gen-reverse-zones.py` | `zone_file` `-o` `-n` `-e` `-t` `--print-conf` `--dry-run` |
| `dns-query-test` | `tools/dns/dns-query-test.py` | `--name` `--type` `--server` |
| `zone-consistency-check` | `tools/dns/zone-consistency-check.py` | `zone_file` `--server` |
| `ipa-health-check` | `tools/freeipa/ipa-health-check.py` | `--server` |
| `ipa-user-report` | `tools/freeipa/ipa-user-report.py` | `--locked` `--expiring` |
| `ipa-host-inventory` | `tools/freeipa/ipa-host-inventory.py` | _(none)_ |
| `cert-inventory` | `tools/certs/cert-inventory.py` | `--path` |
| `cert-expiry-check` | `tools/certs/cert-expiry-check.py` | `--days` `--path` |
| `sysinfo` | `tools/system/sysinfo.py` | _(none)_ |
| `service-status` | `tools/system/service-status.py` | `--service` `--all-failed` |
| `troubleshoot` | `tools/system/troubleshoot.py` | _(none)_ |
| `vm-list` | `tools/kvm/vm-list.py` | `--running` |
| `vm-snapshot-report` | `tools/kvm/vm-snapshot-report.py` | `--days` |
| `repo-health` | `tools/dnf/repo-health.py` | _(none)_ |
| `updates-available` | `tools/dnf/updates-available.py` | `--security-only` |
| `container-status` | `tools/docker/container-status.py` | `--running` |
| `compose-health` | `tools/docker/compose-health.py` | `--path` |
| `connectivity-check` | `tools/network/connectivity-check.py` | `--host` |
| `port-scan` | `tools/network/port-scan.py` | `--target` `--local` `--timeout` |
| `journal-errors` | `tools/logs/journal-errors.py` | `--hours` `--unit` `--top` |
| `log-summary` | `tools/logs/log-summary.py` | `--file` `--pattern` |

---

## Universal Flags

Every tool (except `gen-reverse-zones.py`) accepts these flags:

| Flag | Description |
|------|-------------|
| `--json` | Emit machine-readable JSON to stdout instead of human output |
| `--no-color` | Disable ANSI color codes (auto-detected on non-TTY) |
| `--quiet` | Suppress informational output (warnings and errors still shown) |
| `--config PATH` | Override config file path (default: `~/.lrn_tools/config.ini`) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — all checks passed |
| `1` | Error — hard failure, tool could not complete or critical threshold exceeded |
| `2` | Warning — tool ran successfully but found issues below critical threshold |

The `cert-expiry-check` tool specifically uses these codes so it can be called from cron or monitoring.

---

## JSON Output Schema

All JSON-capable tools emit a consistent top-level structure:

```json
{
  "tool": "sysinfo",
  "timestamp": "2026-04-11T15:00:00Z",
  "status": "ok",
  "summary": "One-line human summary",
  "records": [
    { "column_a": "value", "column_b": "value", "Status": "OK" }
  ],
  "errors": []
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `status` | `ok` / `warn` / `crit` / `error` / `mixed` | Overall tool result |
| `records` | array of objects | Data rows; schema is tool-specific |
| `errors` | array of strings | Non-fatal errors encountered during the run |

The web dashboard consumes this schema to render status badges and sortable tables.
