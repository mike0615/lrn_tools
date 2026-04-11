#!/usr/bin/env python3
"""System Info — display OS, kernel, CPU, RAM, disk, uptime, SELinux, FIPS."""

import os, sys, platform, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput, format_bytes)
from lib.config import load_config


def _read(path, default=''):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


def collect():
    data = {}

    # OS / identity
    data['hostname'] = platform.node()
    data['fqdn'] = run_cmd(['hostname', '-f']).stdout or platform.node()

    rel = {}
    for line in _read('/etc/os-release').splitlines():
        if '=' in line:
            k, _, v = line.partition('=')
            rel[k.strip()] = v.strip().strip('"')
    data['os_name']    = rel.get('PRETTY_NAME', platform.system())
    data['os_version'] = rel.get('VERSION_ID', '')
    data['kernel']     = platform.release()

    # Uptime
    try:
        secs = float(_read('/proc/uptime').split()[0])
        d, rem = divmod(int(secs), 86400)
        h, rem = divmod(rem, 3600)
        m, s   = divmod(rem, 60)
        data['uptime'] = f"{d}d {h}h {m}m {s}s"
    except Exception:
        data['uptime'] = 'unknown'

    # CPU
    cpuinfo = _read('/proc/cpuinfo')
    model_lines = [l for l in cpuinfo.splitlines() if l.startswith('model name')]
    data['cpu_model'] = model_lines[0].split(':', 1)[1].strip() if model_lines else 'unknown'
    data['cpu_count'] = str(cpuinfo.count('processor\t:'))

    # RAM
    meminfo = {}
    for line in _read('/proc/meminfo').splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meminfo[k.strip()] = v.strip()
    total_kb = int(meminfo.get('MemTotal', '0 kB').split()[0])
    avail_kb = int(meminfo.get('MemAvailable', '0 kB').split()[0])
    used_kb  = total_kb - avail_kb
    data['ram_total']     = format_bytes(total_kb * 1024)
    data['ram_used']      = format_bytes(used_kb * 1024)
    data['ram_available'] = format_bytes(avail_kb * 1024)

    # Load average
    try:
        la = os.getloadavg()
        data['load_avg'] = f"{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}"
    except Exception:
        data['load_avg'] = 'unknown'

    # SELinux
    r = run_cmd(['getenforce'])
    data['selinux'] = r.stdout if r.returncode == 0 else 'Not installed'

    # FIPS
    fips_val = _read('/proc/sys/crypto/fips_enabled', '0')
    data['fips'] = 'Enabled' if fips_val == '1' else 'Disabled'

    # Timezone
    r = run_cmd(['timedatectl', 'show', '--property=Timezone', '--value'])
    data['timezone'] = r.stdout or 'unknown'

    # Time sync
    r = run_cmd(['timedatectl', 'show', '--property=NTPSynchronized', '--value'])
    data['ntp_sync'] = r.stdout or 'unknown'

    # Disk
    disks = []
    r = run_cmd(['df', '-h', '--output=target,size,used,avail,pcent,fstype', '-x', 'tmpfs', '-x', 'devtmpfs'])
    if r.returncode == 0:
        lines = r.stdout.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks.append({
                    'Mount':   parts[0],
                    'Size':    parts[1],
                    'Used':    parts[2],
                    'Avail':   parts[3],
                    'Use%':    parts[4],
                    'FSType':  parts[5],
                })
    data['disks'] = disks

    return data


def main():
    parser = make_base_parser('Display comprehensive system information for this Rocky Linux host')
    args = parser.parse_args()
    apply_base_args(args)

    info = collect()

    if args.json:
        out = ToolOutput(
            tool='sysinfo',
            status='ok',
            summary=f"{info['fqdn']} — {info['os_name']} | up {info['uptime']}",
            records=[{k: v for k, v in info.items() if k != 'disks'}] + info.get('disks', []),
        )
        # Flatten for clean JSON
        out.records = [
            {
                'section': 'system',
                'hostname': info['hostname'],
                'fqdn': info['fqdn'],
                'os': info['os_name'],
                'kernel': info['kernel'],
                'uptime': info['uptime'],
                'load_avg': info['load_avg'],
                'cpu_model': info['cpu_model'],
                'cpu_count': info['cpu_count'],
                'ram_total': info['ram_total'],
                'ram_used': info['ram_used'],
                'ram_available': info['ram_available'],
                'selinux': info['selinux'],
                'fips': info['fips'],
                'timezone': info['timezone'],
                'ntp_sync': info['ntp_sync'],
            }
        ] + [dict(section='disk', **d) for d in info.get('disks', [])]
        emit_json(out)

    print_header(f"System Info — {info['fqdn']}")

    print_section('Identity')
    rows = [
        {'Key': 'Hostname',     'Value': info['hostname']},
        {'Key': 'FQDN',         'Value': info['fqdn']},
        {'Key': 'OS',           'Value': info['os_name']},
        {'Key': 'Kernel',       'Value': info['kernel']},
        {'Key': 'Uptime',       'Value': info['uptime']},
        {'Key': 'Load Avg',     'Value': info['load_avg']},
        {'Key': 'Timezone',     'Value': info['timezone']},
        {'Key': 'NTP Synced',   'Value': info['ntp_sync']},
    ]
    print_table(rows, columns=['Key', 'Value'])

    print_section('Resources')
    rows = [
        {'Key': 'CPU Model',    'Value': info['cpu_model']},
        {'Key': 'CPU Count',    'Value': info['cpu_count']},
        {'Key': 'RAM Total',    'Value': info['ram_total']},
        {'Key': 'RAM Used',     'Value': info['ram_used']},
        {'Key': 'RAM Available','Value': info['ram_available']},
    ]
    print_table(rows, columns=['Key', 'Value'])

    print_section('Security')
    rows = [
        {'Key': 'SELinux', 'Value': info['selinux']},
        {'Key': 'FIPS',    'Value': info['fips']},
    ]
    print_table(rows, columns=['Key', 'Value'])

    if info.get('disks'):
        print_section('Disk Usage')
        print_table(info['disks'], columns=['Mount', 'Size', 'Used', 'Avail', 'Use%', 'FSType'])


if __name__ == '__main__':
    main()
