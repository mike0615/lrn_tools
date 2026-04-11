#!/usr/bin/env python3
"""KVM Snapshot Report — list snapshots per VM and flag stale ones."""

import os, sys, datetime, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput, require_command)
from lib.config import load_config


def get_vm_names(uri):
    r = run_cmd(['virsh', '-c', uri, 'list', '--all', '--name'], timeout=15)
    if r.returncode != 0:
        return []
    return [n.strip() for n in r.stdout.splitlines() if n.strip()]


def get_snapshots(vm, uri, stale_days):
    r = run_cmd(['virsh', '-c', uri, 'snapshot-list', vm, '--parent'], timeout=15)
    if r.returncode != 0:
        return []

    snaps = []
    for line in r.stdout.splitlines()[2:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]

        # Get snapshot creation time
        r2 = run_cmd(['virsh', '-c', uri, 'snapshot-info', vm, name], timeout=10)
        created = ''
        for l in r2.stdout.splitlines():
            if l.strip().startswith('Creation Time:'):
                created = l.split(':', 1)[1].strip()
                break

        days_old = None
        is_stale = False
        if created:
            try:
                dt = datetime.datetime.strptime(created, '%Y-%m-%d %H:%M:%S %z')
                days_old = (datetime.datetime.now(datetime.timezone.utc) - dt).days
                is_stale = days_old > stale_days
            except Exception:
                pass

        status = 'WARN' if is_stale else 'OK'
        snaps.append({
            'VM':       vm,
            'Snapshot': name,
            'Created':  created or 'unknown',
            'Days Old': str(days_old) if days_old is not None else '?',
            'Stale':    'YES' if is_stale else 'no',
            'Status':   status,
        })
    return snaps


def main():
    parser = make_base_parser('Report KVM VM snapshots and flag stale ones')
    parser.add_argument('--days', type=int, help='Stale threshold in days (overrides config)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    require_command('virsh', 'dnf install libvirt-client')

    uri        = cfg.libvirt_uri
    stale_days = args.days if args.days is not None else cfg.snapshot_stale_days
    vms        = get_vm_names(uri)

    all_rows = []
    for vm in vms:
        all_rows.extend(get_snapshots(vm, uri, stale_days))

    if not all_rows:
        all_rows = [{'VM': '(no snapshots found)', 'Snapshot': '', 'Created': '',
                     'Days Old': '', 'Stale': '', 'Status': 'OK'}]

    overall = 'warn' if any(r['Status'] == 'WARN' for r in all_rows) else 'ok'

    if args.json:
        out = ToolOutput(
            tool='kvm-snapshot-report',
            status=overall,
            summary=f"{len(all_rows)} snapshots — {sum(1 for r in all_rows if r.get('Stale')=='YES')} stale",
            records=all_rows,
        )
        emit_json(out)

    print_header('KVM Snapshot Report')
    print(f"  Stale threshold: {stale_days} days\n")
    print_table(all_rows, columns=['VM', 'Snapshot', 'Created', 'Days Old', 'Stale', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
