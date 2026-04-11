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

## Upcoming / Planned

Tools planned for future releases (not committed to a schedule):

| Tool | Category | Description |
|------|----------|-------------|
| `freeipa-user-import.py` | LDAP / IAM | Bulk import users into FreeIPA from CSV |
| `check-zone-consistency.py` | DNS | Cross-validate forward and reverse zones for missing/mismatched records |
| `named-conf-audit.py` | DNS | Audit named.conf for common misconfigurations |
| `xcpng-snapshot-report.py` | Virtualization | Report on XCP-ng VM snapshots, age, and disk usage |
| `ansible-inv-from-ipa.py` | Automation | Generate Ansible inventory from FreeIPA host records |
