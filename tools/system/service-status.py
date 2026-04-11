#!/usr/bin/env python3
"""Service Status — check critical systemd services and optionally all failed units."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json,
                         ToolOutput, status_badge, print_warn)
from lib.config import load_config


def check_service(name):
    active = run_cmd(['systemctl', 'is-active', name])
    enabled = run_cmd(['systemctl', 'is-enabled', name])
    state = active.stdout.strip() or 'unknown'
    en    = enabled.stdout.strip() or 'unknown'
    status = 'ok' if state == 'active' else ('warn' if state in ('activating', 'reloading') else 'error')
    return {
        'Service': name,
        'Active':  state,
        'Enabled': en,
        'Status':  status.upper(),
    }


def get_all_failed():
    r = run_cmd(['systemctl', '--failed', '--no-legend', '--no-pager', '--plain'])
    rows = []
    if r.returncode == 0 and r.stdout:
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                rows.append({
                    'Unit':   parts[0],
                    'Load':   parts[1],
                    'Active': parts[2],
                    'Sub':    parts[3],
                    'Status': 'FAILED',
                })
    return rows


def main():
    parser = make_base_parser('Check systemd service status for critical and/or failed units')
    parser.add_argument('--service', help='Comma-separated services to check (overrides config)')
    parser.add_argument('--all-failed', action='store_true', help='Show all failed units system-wide')
    args = parser.parse_args()
    apply_base_args(args)

    cfg = load_config(args.config)

    if args.service:
        services = [s.strip() for s in args.service.split(',') if s.strip()]
    else:
        services = cfg.critical_services

    rows = [check_service(s) for s in services]
    failed_rows = get_all_failed() if args.all_failed else []

    overall = 'ok'
    if any(r['Status'] == 'ERROR' for r in rows) or failed_rows:
        overall = 'error'
    elif any(r['Status'] == 'WARN' for r in rows):
        overall = 'warn'

    if args.json:
        out = ToolOutput(
            tool='service-status',
            status=overall,
            summary=f"{sum(1 for r in rows if r['Status']=='OK')}/{len(rows)} critical services active",
            records=[{**r, 'section': 'critical'} for r in rows] +
                    [{**r, 'section': 'failed'}    for r in failed_rows],
        )
        emit_json(out)

    print_header('Service Status')
    print_section(f'Critical Services ({len(services)} checked)')
    print_table(rows, columns=['Service', 'Active', 'Enabled', 'Status'], status_col='Status')

    if args.all_failed:
        print_section('All Failed Units')
        if failed_rows:
            print_table(failed_rows, columns=['Unit', 'Load', 'Active', 'Sub', 'Status'], status_col='Status')
        else:
            print('  No failed units found.\n')


if __name__ == '__main__':
    main()
