#!/usr/bin/env python3
"""
lib/config.py — Configuration loader for lrn_tools.

Reads ~/.lrn_tools/config.ini (or a path passed at runtime).
Exposes a Config class with typed accessors and sensible defaults.
"""

import configparser
import os
from typing import List, Optional


class ConfigError(Exception):
    pass


_DEFAULTS = {
    'general': {
        'site_name': 'LRN Lab',
        'default_format': 'table',
        'tool_timeout': '60',
    },
    'ipa': {
        'server': '',
        'realm': '',
        'admin_principal': '',
        'keytab_path': '',
    },
    'dns': {
        'servers': '127.0.0.1',
        'domain': '',
        'named_conf': '/etc/named.conf',
        'zone_dir': '/var/named',
    },
    'certs': {
        'scan_paths': '/etc/pki/tls/certs\n/etc/ipa/ca.crt',
        'warn_days': '30',
        'critical_days': '7',
        'ipa_nssdb': '',
    },
    'services': {
        'critical_services': 'named,chronyd',
    },
    'kvm': {
        'libvirt_uri': 'qemu:///system',
        'snapshot_stale_days': '14',
    },
    'docker': {
        'compose_paths': '',
    },
    'network': {
        'check_hosts': '',
        'port_checks': '',
    },
    'logs': {
        'watch_files': '/var/log/messages',
        'patterns': '',
    },
    'web': {
        'host': '127.0.0.1',
        'port': '5000',
        'secret_key': 'change-me-in-production',
        'debug': 'false',
    },
    'tui': {
        'color_scheme': 'default',
    },
}


class Config:
    def __init__(self, path: Optional[str] = None):
        self._path = path or os.path.expanduser('~/.lrn_tools/config.ini')
        self._cp = configparser.ConfigParser()

        # Load defaults
        for section, values in _DEFAULTS.items():
            self._cp[section] = values

        # Overlay with file if it exists
        if os.path.isfile(self._path):
            self._cp.read(self._path)

    def _get(self, section: str, key: str) -> str:
        return self._cp.get(section, key, fallback='')

    def require(self, section: str, key: str) -> str:
        val = self._get(section, key).strip()
        if not val:
            raise ConfigError(
                f"Required config key [{section}] {key} is not set.\n"
                f"Edit {self._path} and set this value."
            )
        return val

    def _list(self, section: str, key: str) -> List[str]:
        """Return a multi-line or comma-separated config value as a list of strings."""
        raw = self._get(section, key)
        items = []
        for item in re.split(r'[\n,]', raw):
            item = item.strip()
            if item:
                items.append(item)
        return items

    # ── general ──────────────────────────────────────────────────────────────

    @property
    def site_name(self) -> str:
        return self._get('general', 'site_name') or 'LRN Lab'

    @property
    def tool_timeout(self) -> int:
        return int(self._get('general', 'tool_timeout') or 60)

    # ── ipa ───────────────────────────────────────────────────────────────────

    @property
    def ipa_server(self) -> str:
        return self._get('ipa', 'server').strip()

    @property
    def ipa_realm(self) -> str:
        realm = self._get('ipa', 'realm').strip()
        if not realm and self.ipa_server:
            # Derive from server hostname: ipa01.lrn.local -> LRN.LOCAL
            parts = self.ipa_server.split('.')[1:]
            realm = '.'.join(parts).upper()
        return realm

    @property
    def ipa_admin_principal(self) -> str:
        return self._get('ipa', 'admin_principal').strip()

    @property
    def ipa_keytab(self) -> str:
        return self._get('ipa', 'keytab_path').strip()

    # ── dns ───────────────────────────────────────────────────────────────────

    @property
    def dns_servers(self) -> List[str]:
        return self._list('dns', 'servers') or ['127.0.0.1']

    @property
    def dns_domain(self) -> str:
        return self._get('dns', 'domain').strip()

    @property
    def named_conf(self) -> str:
        return self._get('dns', 'named_conf') or '/etc/named.conf'

    @property
    def zone_dir(self) -> str:
        return self._get('dns', 'zone_dir') or '/var/named'

    # ── certs ─────────────────────────────────────────────────────────────────

    @property
    def cert_scan_paths(self) -> List[str]:
        return self._list('certs', 'scan_paths')

    @property
    def cert_warn_days(self) -> int:
        return int(self._get('certs', 'warn_days') or 30)

    @property
    def cert_critical_days(self) -> int:
        return int(self._get('certs', 'critical_days') or 7)

    @property
    def ipa_nssdb(self) -> str:
        return self._get('certs', 'ipa_nssdb').strip()

    # ── services ──────────────────────────────────────────────────────────────

    @property
    def critical_services(self) -> List[str]:
        return self._list('services', 'critical_services')

    # ── kvm ───────────────────────────────────────────────────────────────────

    @property
    def libvirt_uri(self) -> str:
        return self._get('kvm', 'libvirt_uri') or 'qemu:///system'

    @property
    def snapshot_stale_days(self) -> int:
        return int(self._get('kvm', 'snapshot_stale_days') or 14)

    # ── docker ────────────────────────────────────────────────────────────────

    @property
    def compose_paths(self) -> List[str]:
        return self._list('docker', 'compose_paths')

    # ── network ───────────────────────────────────────────────────────────────

    @property
    def check_hosts(self) -> List[str]:
        return self._list('network', 'check_hosts')

    @property
    def port_checks(self) -> List[str]:
        return self._list('network', 'port_checks')

    # ── logs ──────────────────────────────────────────────────────────────────

    @property
    def watch_files(self) -> List[str]:
        return self._list('logs', 'watch_files')

    @property
    def log_patterns(self) -> dict:
        """Return dict of name->pattern from [logs] patterns."""
        items = {}
        for entry in self._list('logs', 'patterns'):
            if '=' in entry:
                k, _, v = entry.partition('=')
                items[k.strip()] = v.strip()
        return items

    # ── web ───────────────────────────────────────────────────────────────────

    @property
    def web_host(self) -> str:
        return self._get('web', 'host') or '127.0.0.1'

    @property
    def web_port(self) -> int:
        return int(self._get('web', 'port') or 5000)

    @property
    def web_secret_key(self) -> str:
        return self._get('web', 'secret_key') or 'change-me'

    @property
    def web_debug(self) -> bool:
        return self._get('web', 'debug').lower() in ('true', '1', 'yes')


import re  # noqa: E402 — placed here to avoid circular at top


def load_config(path: Optional[str] = None) -> Config:
    """Load and return a Config object. Raises ConfigError on validation failure."""
    return Config(path)
