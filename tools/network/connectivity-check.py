#!/usr/bin/env python3
"""Connectivity Check — ping/TCP sweep of configured hosts with latency reporting."""

import os, sys, socket, subprocess, re, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def icmp_ping(host, count=3, timeout=2):
    """Return (avg_ms, packet_loss_pct) or (None, 100) on failure."""
    r = run_cmd(['ping', '-c', str(count), '-W', str(timeout), host], timeout=timeout * count + 5)
    if r.returncode != 0 and not r.stdout:
        return None, 100

    loss_m = re.search(r'(\d+)% packet loss', r.stdout)
    rtt_m  = re.search(r'rtt .* = [\d.]+/([\d.]+)', r.stdout)

    loss = int(loss_m.group(1)) if loss_m else 100
    avg  = float(rtt_m.group(1)) if rtt_m else None
    return avg, loss


def tcp_connect(host, port, timeout=3):
    """Return (latency_ms, connected)."""
    try:
        start = time.monotonic()
        s = socket.create_connection((host, int(port)), timeout=timeout)
        ms = (time.monotonic() - start) * 1000
        s.close()
        return round(ms, 1), True
    except Exception:
        return None, False


def parse_target(entry):
    """Parse 'host:port:label' or 'host:icmp:label' or just 'host'."""
    parts = entry.split(':')
    host  = parts[0].strip()
    proto = parts[1].strip() if len(parts) > 1 else 'icmp'
    label = parts[2].strip() if len(parts) > 2 else host
    return host, proto, label


def check_target(host, proto, label):
    if proto.lower() in ('icmp', 'ping', ''):
        avg, loss = icmp_ping(host)
        if loss == 0:
            status = 'OK'
        elif loss < 50:
            status = 'WARN'
        else:
            status = 'FAIL'
        return {
            'Label':    label,
            'Host':     host,
            'Protocol': 'ICMP',
            'Port':     '-',
            'Latency':  f"{avg:.1f} ms" if avg else '-',
            'Loss%':    f"{loss}%",
            'Status':   status,
        }
    else:
        ms, ok = tcp_connect(host, proto)
        return {
            'Label':    label,
            'Host':     host,
            'Protocol': 'TCP',
            'Port':     proto,
            'Latency':  f"{ms} ms" if ms else '-',
            'Loss%':    '-',
            'Status':   'OK' if ok else 'FAIL',
        }


def main():
    parser = make_base_parser('Ping/TCP sweep of configured hosts')
    parser.add_argument('--host', action='append', metavar='HOST[:PORT[:LABEL]]',
                        help='Additional host to check (repeatable)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    targets = list(cfg.check_hosts)
    if args.host:
        targets += args.host
    if not targets:
        targets = ['127.0.0.1:icmp:localhost']

    rows = []
    for entry in targets:
        host, proto, label = parse_target(entry)
        row = check_target(host, proto, label)
        rows.append(row)

    overall = ('error' if any(r['Status']=='FAIL' for r in rows) else
               'warn'  if any(r['Status']=='WARN' for r in rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='connectivity-check',
            status=overall,
            summary=f"{sum(1 for r in rows if r['Status']=='OK')}/{len(rows)} targets reachable",
            records=rows,
        )
        emit_json(out)

    print_header('Connectivity Check')
    print_table(rows, columns=['Label', 'Host', 'Protocol', 'Port', 'Latency', 'Loss%', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
