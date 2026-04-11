#!/usr/bin/env python3
"""Journal Errors — query systemd journal for ERROR/CRITICAL entries by unit."""

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def get_journal_errors(hours=24, unit=None):
    cmd = [
        'journalctl',
        '--since', f'{hours} hours ago',
        '--priority=err',
        '--output=json',
        '--no-pager',
    ]
    if unit:
        cmd += ['-u', unit]

    r = run_cmd(cmd, timeout=30)
    if r.returncode != 0:
        return {}, r.stderr

    # Parse NDJSON
    counts  = {}  # unit -> count
    samples = {}  # unit -> last message

    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        svc  = entry.get('_SYSTEMD_UNIT') or entry.get('SYSLOG_IDENTIFIER') or 'kernel'
        msg  = entry.get('MESSAGE', '')
        prio = entry.get('PRIORITY', '3')

        if isinstance(msg, list):
            msg = ' '.join(str(x) for x in msg)
        elif not isinstance(msg, str):
            msg = str(msg)

        counts[svc]  = counts.get(svc, 0) + 1
        samples[svc] = msg[:120]

    return counts, samples


def main():
    parser = make_base_parser('Query systemd journal for errors grouped by unit')
    parser.add_argument('--hours', type=int, default=24,
                        help='Look-back window in hours (default: 24)')
    parser.add_argument('--unit', help='Filter to a specific systemd unit')
    parser.add_argument('--top', type=int, default=20,
                        help='Show top N units by error count (default: 20)')
    args = parser.parse_args()
    apply_base_args(args)

    counts, samples_or_err = get_journal_errors(args.hours, args.unit)

    if isinstance(samples_or_err, str):
        err = samples_or_err
        samples = {}
    else:
        err = ''
        samples = samples_or_err

    rows = []
    for unit, count in sorted(counts.items(), key=lambda x: -x[1])[:args.top]:
        status = 'WARN' if count >= 10 else 'INFO'
        rows.append({
            'Unit':          unit,
            'Error Count':   str(count),
            'Last Message':  samples.get(unit, ''),
            'Status':        status,
        })

    total_errors = sum(counts.values())
    overall = 'warn' if total_errors > 0 else 'ok'

    if args.json:
        out = ToolOutput(
            tool='journal-errors',
            status=overall,
            summary=f"{total_errors} error entries across {len(counts)} units in last {args.hours}h",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header(f'Journal Errors — Last {args.hours} Hours')
    if rows:
        print(f"  Total error entries: {total_errors}   Affected units: {len(counts)}\n")
        print_table(rows, columns=['Unit', 'Error Count', 'Last Message', 'Status'],
                    status_col='Status')
    else:
        print('  No error-level journal entries found in this window.\n')


if __name__ == '__main__':
    main()
