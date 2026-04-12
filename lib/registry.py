"""
lib/registry.py — Single source of truth for all lrn_tools tools.

Both the TUI menu and the web dashboard are built from this list.
To add a new tool: append an entry here — the rest auto-discovers it.
"""

import os

# Project root (two levels up from this file)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _t(path):
    """Return absolute path to a tool relative to project root."""
    return os.path.join(_ROOT, path)


TOOLS = [
    # ── DNS ──────────────────────────────────────────────────────────────────
    {
        "id": "dns-gen-reverse",
        "name": "Generate Reverse Zones",
        "category": "DNS",
        "path": _t("tools/dns/gen-reverse-zones.py"),
        "json_capable": False,
        "description": "Parse a BIND 9 forward zone file and generate reverse lookup zone files with PTR records",
        "args_help": [
            {"flag": "zone_file", "positional": True, "help": "Path to forward zone file"},
            {"flag": "--output-dir", "short": "-o", "help": "Directory to write output files", "default": "."},
            {"flag": "--nameserver", "short": "-n", "help": "Override primary nameserver FQDN"},
            {"flag": "--email", "short": "-e", "help": "Override hostmaster email"},
            {"flag": "--ttl", "short": "-t", "help": "Override default TTL"},
            {"flag": "--print-conf", "short": "-p", "action": "store_true", "help": "Print named.conf stanzas"},
            {"flag": "--no-ipv6", "action": "store_true", "help": "Skip AAAA records"},
            {"flag": "--dry-run", "action": "store_true", "help": "Preview only, do not write files"},
        ],
    },
    {
        "id": "dns-query-test",
        "name": "DNS Query Test",
        "category": "DNS",
        "path": _t("tools/dns/dns-query-test.py"),
        "json_capable": True,
        "description": "Test forward, reverse, SRV, and MX queries against configured DNS servers",
        "args_help": [
            {"flag": "--name", "help": "Hostname or IP to query (default: all from config)"},
            {"flag": "--type", "help": "Record type: A AAAA PTR MX SRV TXT", "default": "A"},
            {"flag": "--server", "help": "Override DNS server(s) to query"},
        ],
    },
    {
        "id": "dns-zone-consistency",
        "name": "Zone Consistency Check",
        "category": "DNS",
        "path": _t("tools/dns/zone-consistency-check.py"),
        "json_capable": True,
        "description": "Cross-validate forward zone A records against their PTR records",
        "args_help": [
            {"flag": "zone_file", "positional": True, "help": "Path to forward zone file"},
            {"flag": "--server", "help": "DNS server to query for PTR lookups"},
        ],
    },
    # ── FreeIPA ───────────────────────────────────────────────────────────────
    {
        "id": "ipa-health",
        "name": "IPA Health Check",
        "category": "FreeIPA",
        "path": _t("tools/freeipa/ipa-health-check.py"),
        "json_capable": True,
        "description": "Check FreeIPA services, replication status, and CA certificate health",
        "args_help": [
            {"flag": "--server", "help": "IPA server hostname (overrides config)"},
        ],
    },
    {
        "id": "ipa-users",
        "name": "User Report",
        "category": "FreeIPA",
        "path": _t("tools/freeipa/ipa-user-report.py"),
        "json_capable": True,
        "description": "List IPA users with lock status, password expiry, and group membership",
        "args_help": [
            {"flag": "--locked", "action": "store_true", "help": "Show only locked accounts"},
            {"flag": "--expiring", "action": "store_true", "help": "Show accounts with expiring passwords"},
        ],
    },
    {
        "id": "ipa-hosts",
        "name": "Host Inventory",
        "category": "FreeIPA",
        "path": _t("tools/freeipa/ipa-host-inventory.py"),
        "json_capable": True,
        "description": "Enumerate all FreeIPA-enrolled hosts with OS, IP, and enrollment info",
        "args_help": [],
    },
    # ── Certificates ──────────────────────────────────────────────────────────
    {
        "id": "cert-inventory",
        "name": "Certificate Inventory",
        "category": "Certificates",
        "path": _t("tools/certs/cert-inventory.py"),
        "json_capable": True,
        "description": "Scan configured paths for PEM certificates and report subject, SAN, issuer, expiry",
        "args_help": [
            {"flag": "--path", "help": "Additional path to scan (can repeat)", "action": "append"},
        ],
    },
    {
        "id": "cert-expiry",
        "name": "Expiry Check",
        "category": "Certificates",
        "path": _t("tools/certs/cert-expiry-check.py"),
        "json_capable": True,
        "description": "Alert on certificates expiring within configured threshold (exit 2=WARN, 1=CRIT)",
        "args_help": [
            {"flag": "--days", "help": "Warning threshold in days", "default": "30", "type": "int"},
        ],
    },
    # ── System ────────────────────────────────────────────────────────────────
    {
        "id": "sys-info",
        "name": "System Info",
        "category": "System",
        "path": _t("tools/system/sysinfo.py"),
        "json_capable": True,
        "description": "Display OS, kernel, CPU, RAM, disk, uptime, SELinux, and FIPS status",
        "args_help": [],
    },
    {
        "id": "service-status",
        "name": "Service Status",
        "category": "System",
        "path": _t("tools/system/service-status.py"),
        "json_capable": True,
        "description": "Check configured critical systemd services for active/failed state",
        "args_help": [
            {"flag": "--service", "help": "Comma-separated service list (overrides config)"},
            {"flag": "--all-failed", "action": "store_true", "help": "Show all failed units system-wide"},
        ],
    },
    {
        "id": "troubleshoot",
        "name": "Automated Triage",
        "category": "System",
        "path": _t("tools/system/troubleshoot.py"),
        "json_capable": True,
        "description": "Run automated diagnostic checks: DNS, time sync, connectivity, Kerberos",
        "args_help": [],
    },
    {
        "id": "sys-status-report",
        "name": "Status Report",
        "category": "System",
        "path": _t("tools/system/status-report.py"),
        "json_capable": True,
        "description": "Full system health sweep: identity, memory, disk, services, network, errors, logins",
        "args_help": [
            {"flag": "--error-hours", "help": "Hours to look back for journal errors (default: 24)", "type": "int"},
        ],
    },
    {
        "id": "sys-software-inventory",
        "name": "Software Inventory",
        "category": "System",
        "path": _t("tools/system/software-inventory.py"),
        "json_capable": True,
        "description": "List installed RPM packages with version, install date, repo, and size",
        "args_help": [
            {"flag": "--recent", "help": "Only packages installed in last N days", "type": "int"},
            {"flag": "--search", "help": "Filter by package name (case-insensitive)"},
            {"flag": "--vendor", "help": "Filter by vendor string"},
            {"flag": "--repo",   "help": "Filter by repository ID"},
            {"flag": "--sort",   "help": "Sort by: name, date, size (default: date)"},
            {"flag": "--top",    "help": "Show top N packages after filtering", "type": "int"},
        ],
    },
    {
        "id": "sys-ssh-keygen",
        "name": "SSH Key Generator",
        "category": "System",
        "path": _t("tools/system/ssh-keygen-tool.py"),
        "json_capable": True,
        "description": "Generate SSH key pairs (ed25519, RSA, ECDSA) and display public key and fingerprint",
        "args_help": [
            {"flag": "--type",   "help": "Key type: ed25519, rsa, ecdsa (default: ed25519)"},
            {"flag": "--bits",   "help": "Key bits — RSA: 4096; ECDSA: 521", "type": "int"},
            {"flag": "--name",   "help": "Key filename (default: id_<type>)"},
            {"flag": "--dir",    "help": "Output directory (default: ~/.ssh)"},
            {"flag": "--comment","help": "Key comment (default: user@host)"},
            {"flag": "--passphrase", "help": "Key passphrase (default: none)"},
            {"flag": "--force",  "action": "store_true", "help": "Overwrite existing key"},
            {"flag": "--list",   "action": "store_true", "help": "List existing keys"},
        ],
    },
    {
        "id": "sys-password-hash",
        "name": "Password Hasher",
        "category": "System",
        "path": _t("tools/system/password-hash.py"),
        "json_capable": True,
        "description": "Hash passwords for /etc/shadow, htpasswd, and other formats using OpenSSL",
        "args_help": [
            {"flag": "--password", "help": "Password to hash (omit to prompt interactively)"},
            {"flag": "--stdin",    "action": "store_true", "help": "Read password from stdin"},
            {"flag": "--format",   "help": "Format: sha512crypt, sha256crypt, md5crypt, htpasswd-apr1, sha256, sha512, all (default: all)"},
        ],
    },
    # ── KVM ───────────────────────────────────────────────────────────────────
    {
        "id": "kvm-vm-list",
        "name": "VM List",
        "category": "KVM",
        "path": _t("tools/kvm/vm-list.py"),
        "json_capable": True,
        "description": "List all KVM guest VMs with state, vCPU, RAM, disk, and autostart status",
        "args_help": [
            {"flag": "--running", "action": "store_true", "help": "Show only running VMs"},
        ],
    },
    {
        "id": "kvm-snapshots",
        "name": "Snapshot Report",
        "category": "KVM",
        "path": _t("tools/kvm/vm-snapshot-report.py"),
        "json_capable": True,
        "description": "List VM snapshots and flag stale ones older than configured threshold",
        "args_help": [
            {"flag": "--days", "help": "Stale threshold in days (overrides config)", "type": "int"},
        ],
    },
    # ── DNF ───────────────────────────────────────────────────────────────────
    {
        "id": "dnf-repos",
        "name": "Repo Health",
        "category": "DNF",
        "path": _t("tools/dnf/repo-health.py"),
        "json_capable": True,
        "description": "Check enabled DNF repositories and test their reachability",
        "args_help": [],
    },
    {
        "id": "dnf-updates",
        "name": "Updates Available",
        "category": "DNF",
        "path": _t("tools/dnf/updates-available.py"),
        "json_capable": True,
        "description": "List available package updates grouped by security, bugfix, and enhancement",
        "args_help": [
            {"flag": "--security-only", "action": "store_true", "help": "Show only security updates"},
        ],
    },
    # ── Docker ────────────────────────────────────────────────────────────────
    {
        "id": "docker-containers",
        "name": "Container Status",
        "category": "Docker",
        "path": _t("tools/docker/container-status.py"),
        "json_capable": True,
        "description": "List all Docker containers with image, status, ports, and restart count",
        "args_help": [
            {"flag": "--running", "action": "store_true", "help": "Show only running containers"},
        ],
    },
    {
        "id": "docker-compose",
        "name": "Compose Health",
        "category": "Docker",
        "path": _t("tools/docker/compose-health.py"),
        "json_capable": True,
        "description": "Check Docker Compose stacks in configured directories for service state",
        "args_help": [
            {"flag": "--path", "help": "Additional compose project directory"},
        ],
    },
    # ── Network ───────────────────────────────────────────────────────────────
    {
        "id": "net-subnet-calc",
        "name": "Subnet Calculator",
        "category": "Network",
        "path": _t("tools/network/subnet-calc.py"),
        "json_capable": True,
        "description": "Calculate subnet details for a CIDR block and optionally split into subnets",
        "args_help": [
            {"flag": "network", "positional": True, "help": "CIDR notation, e.g. 192.168.1.0/24"},
            {"flag": "--split", "help": "Split into subnets of this prefix length (e.g. --split 26)", "type": "int"},
            {"flag": "--list-subnets", "help": "List all subnets of given prefix (capped at 512)", "type": "int"},
        ],
    },
    {
        "id": "net-connectivity",
        "name": "Connectivity Check",
        "category": "Network",
        "path": _t("tools/network/connectivity-check.py"),
        "json_capable": True,
        "description": "Ping/TCP-connect sweep of configured hosts and report latency and status",
        "args_help": [
            {"flag": "--host", "help": "Additional host to check (host:port:label)", "action": "append"},
        ],
    },
    {
        "id": "net-ports",
        "name": "Port Check",
        "category": "Network",
        "path": _t("tools/network/port-scan.py"),
        "json_capable": True,
        "description": "Verify TCP reachability of configured service host:port pairs",
        "args_help": [
            {"flag": "--target", "help": "host:port:description to check", "action": "append"},
        ],
    },
    # ── Logs ──────────────────────────────────────────────────────────────────
    {
        "id": "log-audit",
        "name": "Audit Log",
        "category": "Logs",
        "path": _t("tools/logs/audit-log.py"),
        "json_capable": True,
        "description": "Collect and view Linux audit log events (USER_AUTH, sudo, SELinux, etc.)",
        "args_help": [
            {"flag": "--hours", "help": "Look back N hours (default: 24)", "default": "24", "type": "int"},
            {"flag": "--type",  "help": "Event type filter: USER_AUTH, USER_CMD, AVC, etc. (default: all)"},
            {"flag": "--user",  "help": "Filter by username or UID"},
            {"flag": "--summary", "action": "store_true", "help": "Show summary report via aureport"},
            {"flag": "--top",   "help": "Max events to display (default: 200)", "type": "int"},
        ],
    },
    {
        "id": "log-errors",
        "name": "Journal Errors",
        "category": "Logs",
        "path": _t("tools/logs/journal-errors.py"),
        "json_capable": True,
        "description": "Query systemd journal for ERROR and CRITICAL entries grouped by unit",
        "args_help": [
            {"flag": "--hours", "help": "Look back N hours (default: 24)", "default": "24", "type": "int"},
            {"flag": "--unit", "help": "Filter to specific systemd unit"},
        ],
    },
    {
        "id": "log-summary",
        "name": "Log Summary",
        "category": "Logs",
        "path": _t("tools/logs/log-summary.py"),
        "json_capable": True,
        "description": "Scan configured log files with regex patterns and report match frequency",
        "args_help": [
            {"flag": "--file", "help": "Log file to scan (overrides config)", "action": "append"},
            {"flag": "--hours", "help": "Only scan last N hours of log entries", "type": "int"},
        ],
    },
]

# Grouped view used by TUI and web nav
def get_categories() -> list:
    seen = []
    cats = []
    for t in TOOLS:
        if t['category'] not in seen:
            seen.append(t['category'])
            cats.append(t['category'])
    return cats


def get_tools_by_category() -> dict:
    result = {}
    for t in TOOLS:
        result.setdefault(t['category'], []).append(t)
    return result


def get_tool_by_id(tool_id: str) -> dict:
    for t in TOOLS:
        if t['id'] == tool_id:
            return t
    return None
