#!/usr/bin/env python3
"""Zone Consistency Check — validate A records have matching PTR records."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput,
                         require_command)
from lib.config import load_config


def parse_a_records(zone_file):
    """Extract (fqdn, ip) pairs from a zone file. Handles $ORIGIN."""
    origin = ''
    records = []
    try:
        with open(zone_file) as f:
            raw = f.read()
    except IOError as e:
        return [], str(e)

    flat = re.sub(r'\(([^)]*)\)', lambda m: '(' + m.group(1).replace('\n', ' ') + ')', raw)

    for raw_line in flat.splitlines():
        line = raw_line.rstrip()
        if ';' in line:
            line = line[:line.index(';')].rstrip()
        if not line:
            continue

        m = re.match(r'^\$ORIGIN\s+(\S+)', line, re.IGNORECASE)
        if m:
            origin = m.group(1).rstrip('.') + '.'
            continue

        tokens = line.split()
        if not tokens:
            continue

        # Detect A record: look for token 'A' followed by an IP
        try:
            a_idx = [t.upper() for t in tokens].index('A')
            if a_idx + 1 < len(tokens):
                ip = tokens[a_idx + 1]
                re.match(r'^\d+\.\d+\.\d+\.\d+$', ip)
                if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                    continue
                name = tokens[0] if not raw_line[0].isspace() else '@'
                if name == '@':
                    fqdn = origin
                elif name.endswith('.'):
                    fqdn = name
                elif origin:
                    fqdn = name + '.' + origin
                else:
                    fqdn = name + '.'
                records.append((fqdn, ip))
        except ValueError:
            continue

    return records, ''


def reverse_lookup(ip, server):
    """Query PTR for an IP using dig. Returns answer string."""
    require_command('dig', 'dnf install bind-utils')
    # Build in-addr.arpa name
    parts = ip.split('.')
    arpa = '.'.join(reversed(parts)) + '.in-addr.arpa'
    cmd = ['dig', f'@{server}', arpa, 'PTR', '+short', '+time=3', '+tries=1']
    r = run_cmd(cmd, timeout=8)
    answers = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    if r.timed_out:
        return 'TIMEOUT'
    return answers[0] if answers else 'NXDOMAIN'


def main():
    parser = make_base_parser(
        'Cross-validate forward zone A records against their PTR records'
    )
    parser.add_argument('zone_file', help='Path to forward lookup zone file')
    parser.add_argument('--server', help='DNS server for PTR queries (default: first in config)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    server = args.server or (cfg.dns_servers[0] if cfg.dns_servers else '127.0.0.1')
    records, err = parse_a_records(args.zone_file)

    if err:
        print(f"Error reading zone file: {err}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for fqdn, ip in records:
        ptr = reverse_lookup(ip, server)
        # Normalize for comparison: both should end with .
        fqdn_norm = fqdn.rstrip('.') + '.'
        ptr_norm  = ptr.rstrip('.') + '.' if ptr not in ('NXDOMAIN', 'TIMEOUT') else ptr

        if ptr in ('NXDOMAIN',):
            status = 'WARN'
        elif ptr == 'TIMEOUT':
            status = 'FAIL'
        elif ptr_norm != fqdn_norm:
            status = 'WARN'
        else:
            status = 'OK'

        rows.append({
            'FQDN':   fqdn,
            'IP':     ip,
            'PTR':    ptr,
            'Match':  'yes' if status == 'OK' else 'no',
            'Status': status,
        })

    ok_count   = sum(1 for r in rows if r['Status'] == 'OK')
    overall    = 'ok' if ok_count == len(rows) else ('warn' if any(r['Status']=='WARN' for r in rows) else 'error')

    if args.json:
        out = ToolOutput(
            tool='zone-consistency-check',
            status=overall,
            summary=f"{ok_count}/{len(rows)} A records have matching PTR",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('Zone Consistency Check')
    print(f"  Zone: {args.zone_file}  |  DNS server: {server}")
    print(f"  A records: {len(rows)}  |  Matching PTR: {ok_count}\n")
    print_table(rows, columns=['FQDN', 'IP', 'PTR', 'Match', 'Status'], status_col='Status')


if __name__ == '__main__':
    main()
