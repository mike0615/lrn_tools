#!/usr/bin/env python3
"""IPA Host Inventory — enumerate enrolled hosts with OS, IP, enrollment info."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def get_hosts():
    r = run_cmd(['ipa', 'host-find', '--all', '--sizelimit=0'], timeout=30)
    if r.returncode != 0:
        return [], r.stderr

    hosts = []
    blocks = r.stdout.split('  Host name:')
    for block in blocks[1:]:
        lines = block.splitlines()
        host = {}
        host['Hostname'] = lines[0].strip()
        for line in lines[1:]:
            if ':' in line:
                k, _, v = line.partition(':')
                k = k.strip()
                v = v.strip()
                if k and k not in host:
                    host[k] = v
        hosts.append(host)
    return hosts, ''


def main():
    parser = make_base_parser('Enumerate all FreeIPA-enrolled hosts')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    hosts, err = get_hosts()

    rows = []
    for h in hosts:
        rows.append({
            'Hostname':  h.get('Hostname', ''),
            'IP':        h.get('IP address', h.get('Managed by', '')),
            'OS':        h.get('Operating system', ''),
            'OS Ver':    h.get('OS version', ''),
            'Principal': h.get('Principal name', ''),
            'SSH Key':   'yes' if h.get('SSH public key fingerprint') else 'no',
            'Status':    'OK',
        })

    if not rows:
        rows = [{'Hostname': '(no hosts found or IPA not accessible)',
                 'IP': '', 'OS': '', 'OS Ver': '', 'Principal': '', 'SSH Key': '', 'Status': 'WARN'}]

    if args.json:
        out = ToolOutput(
            tool='ipa-host-inventory',
            status='ok',
            summary=f"{len(rows)} hosts enrolled in FreeIPA",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('FreeIPA Host Inventory')
    print(f"  Enrolled hosts: {len(rows)}\n")
    print_table(rows, columns=['Hostname', 'IP', 'OS', 'OS Ver', 'SSH Key', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
