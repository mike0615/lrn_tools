#!/usr/bin/env python3
"""DNF Updates Available — list available updates grouped by type."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def get_updates(security_only=False):
    cmd = ['dnf', 'check-update', '--quiet']
    if security_only:
        cmd.append('--security')
    r = run_cmd(cmd, timeout=120)
    # exit 100 = updates available, 0 = none, 1 = error
    if r.returncode == 1:
        return [], r.stderr

    packages = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('Last metadata') or line.startswith('Security:'):
            continue
        parts = line.split()
        if len(parts) >= 3 and not line.startswith(' '):
            packages.append({
                'Package': parts[0],
                'Version': parts[1],
                'Repo':    parts[2],
            })
    return packages, ''


def get_security_advisories():
    """Get list of applicable security advisories."""
    r = run_cmd(['dnf', 'updateinfo', 'list', '--security', '--available'], timeout=120)
    if r.returncode != 0:
        return []
    advisories = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            adv_id   = parts[0]
            sev      = parts[1] if len(parts) > 2 else 'unknown'
            pkg      = parts[2] if len(parts) > 2 else ''
            advisories[pkg] = {'advisory': adv_id, 'severity': sev}
    return advisories


def main():
    parser = make_base_parser('List available DNF package updates grouped by type')
    parser.add_argument('--security-only', action='store_true',
                        help='Show only security updates')
    args = parser.parse_args()
    apply_base_args(args)

    packages, err = get_updates(args.security_only)
    advisories    = get_security_advisories()

    rows = []
    for pkg in packages:
        adv_info  = advisories.get(pkg['Package'], {})
        severity  = adv_info.get('severity', '')
        adv_id    = adv_info.get('advisory', '')
        is_sec    = bool(adv_info)

        status = 'WARN' if is_sec and severity.lower() in ('important', 'critical') else 'INFO'

        rows.append({
            'Package':   pkg['Package'],
            'Version':   pkg['Version'],
            'Repo':      pkg['Repo'],
            'Advisory':  adv_id or '-',
            'Severity':  severity or '-',
            'Status':    status,
        })

    # Sort: security updates first
    rows.sort(key=lambda r: (0 if r['Advisory'] != '-' else 1, r['Package']))

    total       = len(rows)
    sec_count   = sum(1 for r in rows if r['Advisory'] != '-')
    overall     = ('warn' if sec_count > 0 else ('ok' if total == 0 else 'info'))

    if args.json:
        out = ToolOutput(
            tool='dnf-updates-available',
            status=overall,
            summary=f"{total} updates available — {sec_count} security",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('DNF Updates Available')
    if not rows:
        print('  System is up to date.\n')
    else:
        print(f"  Total: {total}   Security: {sec_count}\n")
        print_table(rows, columns=['Package', 'Version', 'Repo', 'Advisory', 'Severity', 'Status'],
                    status_col='Status')


if __name__ == '__main__':
    main()
