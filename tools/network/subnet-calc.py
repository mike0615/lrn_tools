#!/usr/bin/env python3
"""
tools/network/subnet-calc.py — Subnet calculator and CIDR breakdown tool.

Supports IPv4 and IPv6. Can split a network into equal subnets.

Usage:
    python3 tools/network/subnet-calc.py 192.168.1.0/24
    python3 tools/network/subnet-calc.py 10.0.0.0/8 --split 24
    python3 tools/network/subnet-calc.py 172.16.0.0/16 --list-subnets 20
"""

import ipaddress
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        C, print_ok, print_warn, print_info)


def analyse(network_str: str) -> dict:
    net = ipaddress.ip_network(network_str, strict=False)
    v4  = (net.version == 4)
    hosts = net.num_addresses - 2 if (v4 and net.prefixlen < 31) else net.num_addresses

    host_list = list(net.hosts())
    first = str(host_list[0])  if host_list else 'N/A'
    last  = str(host_list[-1]) if host_list else 'N/A'

    return {
        'Network':     str(net.network_address),
        'Prefix':      f'/{net.prefixlen}',
        'Netmask':     str(net.netmask)    if v4 else 'N/A',
        'Wildcard':    str(net.hostmask)   if v4 else 'N/A',
        'Broadcast':   str(net.broadcast_address) if v4 else 'N/A',
        'First Host':  first,
        'Last Host':   last,
        'Usable Hosts': f'{hosts:,}',
        'Total Addr':  f'{net.num_addresses:,}',
        'IP Version':  f'IPv{net.version}',
        'CIDR':        str(net),
    }


def split_network(network_str: str, new_prefix: int) -> list:
    net = ipaddress.ip_network(network_str, strict=False)
    if new_prefix <= net.prefixlen:
        return []
    return list(net.subnets(new_prefix=new_prefix))


def main():
    parser = make_base_parser('Subnet calculator and CIDR breakdown tool')
    parser.add_argument('network', help='CIDR notation, e.g. 192.168.1.0/24 or 10.0.0.0/8')
    parser.add_argument('--split', metavar='PREFIX', type=int, default=None,
                        help='Split into subnets of this prefix length (e.g. --split 26)')
    parser.add_argument('--list-subnets', metavar='PREFIX', type=int, default=None,
                        dest='list_subnets',
                        help='List all subnets of prefix length (capped at 512)')
    args = parser.parse_args()
    apply_base_args(args)

    try:
        net = ipaddress.ip_network(args.network, strict=False)
    except ValueError as e:
        print(f'{C.RED}Error:{C.RESET} {e}', file=sys.stderr)
        sys.exit(1)

    info = analyse(str(net))

    # ── JSON output ────────────────────────────────────────────────────────────
    if args.json:
        records = [{'Field': k, 'Value': v, 'Status': 'INFO'} for k, v in info.items()]

        if args.split:
            subnets = split_network(str(net), args.split)
            for i, s in enumerate(subnets[:512]):
                h = list(s.hosts())
                records.append({
                    'Field':  f'Subnet {i+1}',
                    'Value':  f'{s}  ({h[0]} – {h[-1]}, {s.num_addresses-2:,} hosts)' if h else str(s),
                    'Status': 'INFO',
                })

        out = ToolOutput(
            tool='subnet-calc',
            status='ok',
            summary=f'Network: {net}  |  Usable hosts: {info["Usable Hosts"]}',
            records=records,
        )
        emit_json(out)

    # ── Human output ───────────────────────────────────────────────────────────
    print_header('Subnet Calculator', str(net))

    rows = [{'Field': k, 'Value': v} for k, v in info.items()]
    print_table(rows, ['Field', 'Value'])

    if args.split or args.list_subnets:
        prefix = args.split or args.list_subnets
        subnets = split_network(str(net), prefix)
        if not subnets:
            print_warn(f'Cannot split /{net.prefixlen} into /{prefix} subnets (prefix must be larger)')
        else:
            total = len(subnets)
            shown = subnets[:512]
            print_section(f'Subnets  (/{prefix}  —  {total:,} total{"  —  showing first 512" if total > 512 else ""})')
            sub_rows = []
            for s in shown:
                h = list(s.hosts())
                sub_rows.append({
                    'Subnet':      str(s),
                    'First Host':  str(h[0])  if h else 'N/A',
                    'Last Host':   str(h[-1]) if h else 'N/A',
                    'Hosts':       f'{max(0, s.num_addresses - 2):,}',
                })
            print_table(sub_rows, ['Subnet', 'First Host', 'Last Host', 'Hosts'])


if __name__ == '__main__':
    main()
