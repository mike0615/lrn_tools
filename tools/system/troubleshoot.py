#!/usr/bin/env python3
"""Automated Triage — DNS resolution, time sync, connectivity, Kerberos checks."""

import os, sys, socket, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def tcp_check(host, port, timeout=3):
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def check_dns(cfg):
    results = []
    test_names = ['google.com', cfg.ipa_server or 'localhost'] + \
                 [s for s in cfg.dns_servers if s != '127.0.0.1'][:2]
    test_names = list(dict.fromkeys(filter(None, test_names)))

    for name in test_names[:5]:
        try:
            ip = socket.gethostbyname(name)
            results.append({'Check': f'Resolve {name}', 'Result': ip, 'Status': 'PASS'})
        except socket.gaierror as e:
            results.append({'Check': f'Resolve {name}', 'Result': str(e), 'Status': 'FAIL'})
    return results


def check_time_sync():
    results = []
    r = run_cmd(['timedatectl', 'show', '--property=NTPSynchronized,TimeUSec,Timezone'])
    synced = 'unknown'
    timezone = 'unknown'
    for line in r.stdout.splitlines():
        if line.startswith('NTPSynchronized='):
            synced = line.split('=', 1)[1]
        if line.startswith('Timezone='):
            timezone = line.split('=', 1)[1]

    status = 'PASS' if synced == 'yes' else 'WARN'
    results.append({'Check': 'NTP Synchronized', 'Result': synced, 'Status': status})
    results.append({'Check': 'Timezone',          'Result': timezone, 'Status': 'INFO'})

    r2 = run_cmd(['chronyc', 'tracking'], timeout=5)
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            if 'System time' in line:
                results.append({'Check': 'Chrony offset', 'Result': line.split(':', 1)[1].strip(), 'Status': 'INFO'})
                break
    return results


def check_connectivity(cfg):
    results = []
    targets = [
        ('IPA LDAP',   cfg.ipa_server or '', 389),
        ('IPA LDAPS',  cfg.ipa_server or '', 636),
        ('IPA HTTPS',  cfg.ipa_server or '', 443),
        ('IPA Kerb',   cfg.ipa_server or '', 88),
        ('DNS Primary',cfg.dns_servers[0] if cfg.dns_servers else '', 53),
    ]
    for label, host, port in targets:
        if not host:
            continue
        ok = tcp_check(host, port)
        results.append({
            'Check':  f'{label} ({host}:{port})',
            'Result': 'reachable' if ok else 'unreachable',
            'Status': 'PASS' if ok else 'FAIL',
        })
    return results


def check_kerberos(cfg):
    results = []
    r = run_cmd(['klist', '-s'])
    if r.returncode == 0:
        r2 = run_cmd(['klist'])
        ticket_info = r2.stdout.splitlines()[1] if len(r2.stdout.splitlines()) > 1 else 'ticket present'
        results.append({'Check': 'Kerberos ticket', 'Result': ticket_info, 'Status': 'PASS'})
    else:
        results.append({'Check': 'Kerberos ticket', 'Result': 'No valid TGT', 'Status': 'WARN'})
    return results


def check_selinux():
    r = run_cmd(['getenforce'])
    mode = r.stdout.strip() if r.returncode == 0 else 'unknown'
    return [{'Check': 'SELinux mode', 'Result': mode,
             'Status': 'PASS' if mode == 'Enforcing' else 'WARN'}]


def check_disk_space():
    results = []
    r = run_cmd(['df', '-h', '--output=target,pcent', '-x', 'tmpfs', '-x', 'devtmpfs'])
    if r.returncode == 0:
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2:
                pct = int(parts[1].rstrip('%'))
                status = 'PASS' if pct < 80 else ('WARN' if pct < 90 else 'FAIL')
                results.append({'Check': f'Disk {parts[0]}', 'Result': parts[1], 'Status': status})
    return results


def main():
    parser = make_base_parser('Automated triage: DNS, time sync, connectivity, Kerberos')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    sections = {
        'DNS Resolution':   check_dns(cfg),
        'Time Sync':        check_time_sync(),
        'Connectivity':     check_connectivity(cfg),
        'Kerberos':         check_kerberos(cfg),
        'SELinux':          check_selinux(),
        'Disk Space':       check_disk_space(),
    }

    all_rows = []
    for section, rows in sections.items():
        for r in rows:
            all_rows.append({'Section': section, **r})

    fail_count = sum(1 for r in all_rows if r['Status'] == 'FAIL')
    warn_count = sum(1 for r in all_rows if r['Status'] == 'WARN')
    overall = 'ok' if fail_count == 0 and warn_count == 0 else ('error' if fail_count else 'warn')

    if args.json:
        out = ToolOutput(
            tool='troubleshoot',
            status=overall,
            summary=f"{len(all_rows)} checks — {fail_count} FAIL, {warn_count} WARN",
            records=all_rows,
        )
        emit_json(out)

    print_header('Automated Triage')
    for section, rows in sections.items():
        print_section(section)
        print_table(rows, columns=['Check', 'Result', 'Status'], status_col='Status')


if __name__ == '__main__':
    main()
