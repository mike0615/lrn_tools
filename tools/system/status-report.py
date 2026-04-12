#!/usr/bin/env python3
"""
tools/system/status-report.py — Comprehensive system status report.

Performs a broad health sweep: system identity, resources, services,
network, security posture, and recent errors — all in one pass.
Suitable for daily operator briefings or pre/post-change snapshots.

Usage:
    python3 tools/system/status-report.py
    python3 tools/system/status-report.py --json
"""

import datetime
import os
import platform
import re
import socket
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        run_cmd, C, print_ok, print_warn, print_info,
                        print_error, format_bytes, status_badge)


def _read(path: str, default='') -> str:
    try:
        return open(path).read().strip()
    except Exception:
        return default


def _run(cmd, timeout=10) -> str:
    r = run_cmd(cmd, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 else ''


# ── Collectors ─────────────────────────────────────────────────────────────────

def collect_identity() -> list:
    hostname  = socket.getfqdn()
    os_id     = _read('/etc/os-release').split('\n')
    os_name   = next((l.split('=',1)[1].strip('"') for l in os_id if l.startswith('PRETTY_NAME=')), platform.version())
    kernel    = platform.release()
    arch      = platform.machine()
    uptime_s  = float(_read('/proc/uptime', '0').split()[0])
    days      = int(uptime_s // 86400)
    hours     = int((uptime_s % 86400) // 3600)
    mins      = int((uptime_s % 3600) // 60)

    load = _read('/proc/loadavg', '? ? ?').split()[:3]
    load_str  = '  '.join(load) if load else '?'

    fips      = _read('/proc/sys/crypto/fips_enabled', '0')
    selinux   = _run(['getenforce']) or 'Unknown'

    return [
        {'Field': 'Hostname',    'Value': hostname,                       'Status': 'INFO'},
        {'Field': 'OS',          'Value': os_name,                        'Status': 'INFO'},
        {'Field': 'Kernel',      'Value': kernel,                         'Status': 'INFO'},
        {'Field': 'Arch',        'Value': arch,                           'Status': 'INFO'},
        {'Field': 'Uptime',      'Value': f'{days}d {hours}h {mins}m',    'Status': 'OK'},
        {'Field': 'Load Avg',    'Value': load_str,                       'Status': 'INFO'},
        {'Field': 'SELinux',     'Value': selinux,                        'Status': 'OK' if selinux == 'Enforcing' else 'WARN'},
        {'Field': 'FIPS',        'Value': 'Enabled' if fips == '1' else 'Disabled', 'Status': 'OK' if fips == '1' else 'INFO'},
        {'Field': 'Report Time', 'Value': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Status': 'INFO'},
    ]


def collect_memory() -> list:
    meminfo = {}
    for line in _read('/proc/meminfo').splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meminfo[k.strip()] = int(v.strip().split()[0]) * 1024  # kB -> bytes

    total   = meminfo.get('MemTotal', 0)
    free    = meminfo.get('MemAvailable', 0)
    used    = total - free
    pct     = int(used / total * 100) if total else 0
    status  = 'ERROR' if pct >= 90 else ('WARN' if pct >= 75 else 'OK')

    swap_total = meminfo.get('SwapTotal', 0)
    swap_free  = meminfo.get('SwapFree', 0)
    swap_used  = swap_total - swap_free
    swap_pct   = int(swap_used / swap_total * 100) if swap_total else 0
    swap_status = 'WARN' if swap_pct >= 50 else 'OK'

    return [
        {'Resource': 'RAM Total',     'Value': format_bytes(total),    'Used %': f'{pct}%',      'Status': status},
        {'Resource': 'RAM Available', 'Value': format_bytes(free),     'Used %': '',             'Status': 'INFO'},
        {'Resource': 'Swap Total',    'Value': format_bytes(swap_total),'Used %': f'{swap_pct}%', 'Status': swap_status},
    ]


def collect_disk() -> list:
    r = run_cmd(['df', '-h', '--output=target,fstype,size,used,avail,pcent'], timeout=10)
    rows = []
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        mp, fstype, size, used, avail, pct_str = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        if fstype in ('tmpfs', 'devtmpfs', 'squashfs', 'overlay', 'efivarfs'):
            continue
        try:
            pct = int(pct_str.rstrip('%'))
        except ValueError:
            pct = 0
        status = 'ERROR' if pct >= 90 else ('WARN' if pct >= 80 else 'OK')
        rows.append({
            'Mount':  mp,
            'Size':   size,
            'Used':   used,
            'Avail':  avail,
            'Use%':   pct_str,
            'Status': status,
        })
    return rows


def collect_services() -> list:
    """Check critical services using systemctl."""
    critical = [
        'sshd', 'chronyd', 'firewalld', 'auditd',
        'crond', 'rsyslog', 'sssd', 'named', 'httpd',
        'dirsrv@LRN-LOCAL', 'krb5kdc', 'kadmin', 'ipa',
    ]
    rows = []
    for svc in critical:
        r = run_cmd(['systemctl', 'is-active', svc], timeout=5)
        state = r.stdout.strip()
        if state == 'active':
            status = 'OK'
        elif state in ('inactive', 'unknown'):
            status = 'INFO'
        else:
            status = 'WARN'
        rows.append({'Service': svc, 'State': state, 'Status': status})
    return rows


def collect_network() -> list:
    rows = []
    # IP addresses
    r = run_cmd(['ip', '-o', 'addr', 'show', 'scope', 'global'], timeout=5)
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface = parts[1]
        proto = parts[2]
        addr  = parts[3]
        rows.append({'Interface': iface, 'Protocol': proto, 'Address': addr, 'Status': 'INFO'})

    # Default gateway
    r = run_cmd(['ip', 'route', 'show', 'default'], timeout=5)
    if r.stdout.strip():
        rows.append({'Interface': 'gateway', 'Protocol': 'route', 'Address': r.stdout.strip(), 'Status': 'INFO'})

    # DNS servers
    try:
        for line in open('/etc/resolv.conf'):
            if line.startswith('nameserver'):
                rows.append({'Interface': 'DNS', 'Protocol': 'nameserver', 'Address': line.split()[1], 'Status': 'INFO'})
    except Exception:
        pass

    return rows


def collect_time_sync() -> list:
    r = run_cmd(['timedatectl', 'show', '--no-pager'], timeout=5)
    info = {}
    for line in r.stdout.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            info[k.strip()] = v.strip()

    synced  = info.get('NTPSynchronized', 'no') == 'yes'
    service = info.get('NTP', 'no')              == 'yes'
    tz      = info.get('Timezone', '?')

    # chronyc tracking for offset
    cr = run_cmd(['chronyc', 'tracking'], timeout=5)
    offset = 'unknown'
    for line in cr.stdout.splitlines():
        if 'System time' in line:
            m = re.search(r'([\d.]+)\s+seconds', line)
            if m:
                offset = f'{float(m.group(1))*1000:.3f} ms'

    status = 'OK' if synced else 'WARN'
    return [
        {'Check': 'NTP Synchronized', 'Value': str(synced),     'Status': status},
        {'Check': 'NTP Service',       'Value': str(service),    'Status': 'OK' if service else 'WARN'},
        {'Check': 'Timezone',          'Value': tz,              'Status': 'INFO'},
        {'Check': 'Clock Offset',      'Value': offset,          'Status': 'INFO'},
    ]


def collect_journal_errors(hours: int = 24) -> list:
    r = run_cmd(
        ['journalctl', '--since', f'{hours} hours ago', '--priority=err',
         '--no-pager', '--output=short-iso', '-n', '20'],
        timeout=20
    )
    rows = []
    for line in r.stdout.splitlines()[-20:]:
        rows.append({'Time': line[:25], 'Message': line[25:95], 'Status': 'WARN'})
    return rows


def collect_logins() -> list:
    """Last 10 successful and failed logins."""
    rows = []
    r = run_cmd(['last', '-n', '10', '-F'], timeout=5)
    for line in r.stdout.splitlines():
        if not line.strip() or line.startswith('wtmp'):
            continue
        rows.append({'Entry': line.strip(), 'Status': 'INFO'})
    return rows[:10]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = make_base_parser('Comprehensive system status report')
    parser.add_argument('--error-hours', type=int, default=24,
                        help='Hours to look back for journal errors (default: 24)')
    args = parser.parse_args()
    apply_base_args(args)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    identity_rows = collect_identity()
    memory_rows   = collect_memory()
    disk_rows     = collect_disk()
    service_rows  = collect_services()
    network_rows  = collect_network()
    time_rows     = collect_time_sync()
    error_rows    = collect_journal_errors(args.error_hours)
    login_rows    = collect_logins()

    # Compute overall status
    all_statuses = (
        [r['Status'] for r in identity_rows] +
        [r['Status'] for r in memory_rows] +
        [r['Status'] for r in disk_rows] +
        [r['Status'] for r in service_rows] +
        [r['Status'] for r in time_rows]
    )
    if 'ERROR' in all_statuses:
        overall = 'error'
    elif 'WARN' in all_statuses:
        overall = 'warn'
    else:
        overall = 'ok'

    # ── JSON ───────────────────────────────────────────────────────────────────
    if args.json:
        records = []
        for section, rows in [
            ('identity', identity_rows), ('memory', memory_rows),
            ('disk', disk_rows), ('services', service_rows),
            ('network', network_rows), ('time', time_rows),
            ('errors', error_rows), ('logins', login_rows),
        ]:
            for r in rows:
                r['section'] = section
                records.append(r)

        emit_json(ToolOutput(
            tool='status-report',
            status=overall,
            summary=f'System status as of {now}',
            records=records,
        ))

    # ── Human output ───────────────────────────────────────────────────────────
    hostname = socket.getfqdn()
    print_header('System Status Report', f'{hostname}  —  {now}')

    print_section('System Identity')
    print_table(identity_rows, ['Field', 'Value', 'Status'], status_col='Status')

    print_section('Memory & Swap')
    print_table(memory_rows, ['Resource', 'Value', 'Used %', 'Status'], status_col='Status')

    print_section('Disk Usage')
    if disk_rows:
        print_table(disk_rows, ['Mount', 'Size', 'Used', 'Avail', 'Use%', 'Status'], status_col='Status')
    else:
        print_info('No disk data available.')

    print_section('Critical Services')
    print_table(service_rows, ['Service', 'State', 'Status'], status_col='Status')

    print_section('Network Interfaces & DNS')
    if network_rows:
        print_table(network_rows, ['Interface', 'Protocol', 'Address', 'Status'], status_col='Status')
    else:
        print_info('No network data.')

    print_section('Time Synchronization')
    print_table(time_rows, ['Check', 'Value', 'Status'], status_col='Status')

    print_section(f'Recent Journal Errors  (last {args.error_hours}h  —  max 20)')
    if error_rows:
        print_table(error_rows, ['Time', 'Message', 'Status'], status_col='Status')
    else:
        print_ok('No error-level journal entries found.')

    print_section('Recent Logins')
    if login_rows:
        for r in login_rows:
            print(f'  {C.DIM}{r["Entry"]}{C.RESET}')
    else:
        print_info('No login history available.')

    rc = 1 if overall == 'error' else (2 if overall == 'warn' else 0)
    sys.exit(rc)


if __name__ == '__main__':
    main()
