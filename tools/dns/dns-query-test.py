#!/usr/bin/env python3
"""DNS Query Test — test forward/reverse/SRV queries against configured DNS servers."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput,
                         require_command)
from lib.config import load_config


RECORD_TYPES = ('A', 'AAAA', 'PTR', 'MX', 'SRV', 'TXT', 'NS', 'CNAME', 'SOA')

DEFAULT_TEST_NAMES = ['_ldap._tcp', '_kerberos._tcp', '_kpasswd._tcp']


def dig_query(name, rtype, server, domain=''):
    """Run dig and return list of answer records as strings."""
    require_command('dig', 'dnf install bind-utils')
    fqdn = name if name.endswith('.') or '.' in name else f"{name}.{domain}"
    cmd = ['dig', f'@{server}', fqdn, rtype, '+short', '+time=3', '+tries=1']
    r = run_cmd(cmd, timeout=10)
    answers = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    if r.timed_out or r.returncode not in (0, 9):
        answers = ['TIMEOUT']
    elif not answers:
        answers = ['NXDOMAIN']
    return answers


def query_all_servers(name, rtype, servers, domain):
    rows = []
    results_by_server = {}
    for srv in servers:
        answers = dig_query(name, rtype, srv, domain)
        results_by_server[srv] = answers
        for ans in answers:
            rows.append({
                'Name':   name,
                'Type':   rtype,
                'Server': srv,
                'Answer': ans,
                'Status': 'OK' if ans not in ('TIMEOUT', 'NXDOMAIN') else
                          ('WARN' if ans == 'NXDOMAIN' else 'FAIL'),
            })

    # Flag disagreement across servers
    unique_answers = {frozenset(v) for v in results_by_server.values()}
    if len(unique_answers) > 1:
        for row in rows:
            if row['Status'] == 'OK':
                row['Status'] = 'WARN'
                row['Answer'] += ' [MISMATCH]'
    return rows


def main():
    parser = make_base_parser('Test DNS queries against configured servers')
    parser.add_argument('--name',   help='Hostname or IP to query (default: IPA SRV records)')
    parser.add_argument('--type',   default='A', choices=RECORD_TYPES,
                        help='DNS record type (default: A)')
    parser.add_argument('--server', help='DNS server(s) to query, comma-separated (overrides config)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    servers = [s.strip() for s in args.server.split(',')] if args.server else cfg.dns_servers
    domain  = cfg.dns_domain

    if args.name:
        names = [args.name]
        rtypes = [args.type]
    else:
        # Default: query IPA service records + domain SOA
        names  = []
        rtypes = []
        if domain:
            names.append(domain);  rtypes.append('SOA')
            names.append(domain);  rtypes.append('NS')
        for svc in DEFAULT_TEST_NAMES:
            if domain:
                names.append(f"{svc}.{domain}"); rtypes.append('SRV')

        if not names:
            names  = [cfg.ipa_server or 'localhost']
            rtypes = ['A']

    all_rows = []
    for name, rtype in zip(names, rtypes):
        rows = query_all_servers(name, rtype, servers, domain)
        all_rows.extend(rows)

    overall = ('error' if any(r['Status'] == 'FAIL' for r in all_rows) else
               'warn'  if any(r['Status'] == 'WARN' for r in all_rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='dns-query-test',
            status=overall,
            summary=f"{len(all_rows)} query result(s) across {len(servers)} server(s)",
            records=all_rows,
        )
        emit_json(out)

    print_header('DNS Query Test')
    print_table(all_rows, columns=['Name', 'Type', 'Server', 'Answer', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
