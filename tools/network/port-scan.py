#!/usr/bin/env python3
"""Port Check — verify TCP reachability of configured service host:port pairs."""

import os, sys, socket, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


# Common service port map for reference
WELL_KNOWN = {
    '22': 'SSH', '53': 'DNS', '80': 'HTTP', '88': 'Kerberos',
    '389': 'LDAP', '443': 'HTTPS', '464': 'kpasswd', '636': 'LDAPS',
    '3306': 'MySQL', '5432': 'PostgreSQL', '5985': 'WinRM-HTTP',
    '8080': 'HTTP-Alt', '8443': 'HTTPS-Alt', '9200': 'Elasticsearch',
}


def tcp_check(host, port, timeout=3):
    try:
        start = time.monotonic()
        s = socket.create_connection((host, int(port)), timeout=timeout)
        ms = (time.monotonic() - start) * 1000
        s.close()
        return 'OPEN', round(ms, 1)
    except socket.timeout:
        return 'TIMEOUT', None
    except ConnectionRefusedError:
        return 'REFUSED', None
    except Exception as e:
        return 'ERROR', None


def get_listening_ports():
    """Show locally listening TCP services via ss."""
    r = run_cmd(['ss', '-tlnp', '--no-header'], timeout=10)
    rows = []
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                local = parts[3]
                proc  = parts[6] if len(parts) > 6 else '-'
                # Extract port from address like 0.0.0.0:443 or *:53
                port = local.rsplit(':', 1)[-1]
                svc  = WELL_KNOWN.get(port, '')
                rows.append({
                    'Local Address': local,
                    'Port':          port,
                    'Service':       svc,
                    'Process':       proc,
                })
    return rows


def main():
    parser = make_base_parser('Verify TCP reachability of configured service endpoints')
    parser.add_argument('--target', action='append', metavar='HOST:PORT[:DESCRIPTION]',
                        help='Target to check (repeatable)')
    parser.add_argument('--local', action='store_true',
                        help='Show locally listening ports (via ss)')
    parser.add_argument('--timeout', type=int, default=3, help='TCP connect timeout (default: 3s)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    targets = list(cfg.port_checks)
    if args.target:
        targets += args.target

    rows = []
    for entry in targets:
        parts = entry.split(':')
        if len(parts) < 2:
            continue
        host  = parts[0].strip()
        port  = parts[1].strip()
        desc  = parts[2].strip() if len(parts) > 2 else WELL_KNOWN.get(port, port)

        state, ms = tcp_check(host, port, args.timeout)
        status = 'OK' if state == 'OPEN' else ('WARN' if state == 'TIMEOUT' else 'FAIL')

        rows.append({
            'Host':     host,
            'Port':     port,
            'Service':  desc,
            'State':    state,
            'Latency':  f"{ms} ms" if ms else '-',
            'Status':   status,
        })

    listen_rows = get_listening_ports() if args.local else []

    overall = ('error' if any(r['Status']=='FAIL' for r in rows) else
               'warn'  if any(r['Status']=='WARN' for r in rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='port-scan',
            status=overall,
            summary=f"{sum(1 for r in rows if r['State']=='OPEN')}/{len(rows)} ports open",
            records=[{'section': 'remote', **r} for r in rows] +
                    [{'section': 'local',  **r} for r in listen_rows],
        )
        emit_json(out)

    print_header('Port Check')
    if rows:
        print_section('Remote Port Checks')
        print_table(rows, columns=['Host', 'Port', 'Service', 'State', 'Latency', 'Status'],
                    status_col='Status')
    if args.local:
        print_section('Local Listening Ports')
        if listen_rows:
            print_table(listen_rows, columns=['Local Address', 'Port', 'Service', 'Process'])
        else:
            print('  No listening ports found.\n')
    if not rows and not args.local:
        print('  No targets configured. Set [network] port_checks or use --target.\n')


if __name__ == '__main__':
    main()
