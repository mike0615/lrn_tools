#!/usr/bin/env python3
"""KVM VM List — list all guest VMs with state, vCPU, RAM, disk, autostart."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput, require_command)
from lib.config import load_config


def get_vm_list(uri):
    r = run_cmd(['virsh', '-c', uri, 'list', '--all', '--name'], timeout=15)
    if r.returncode != 0:
        return [], r.stderr
    names = [n.strip() for n in r.stdout.splitlines() if n.strip()]
    return names, ''


def get_vm_info(name, uri):
    info = {'Name': name}

    r = run_cmd(['virsh', '-c', uri, 'dominfo', name], timeout=10)
    for line in r.stdout.splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            k = k.strip(); v = v.strip()
            if k == 'State':        info['State']    = v
            elif k == 'CPU(s)':     info['vCPUs']    = v
            elif k == 'Max memory': info['RAM']      = v
            elif k == 'Autostart':  info['Autostart']= v

    # Disk info
    r2 = run_cmd(['virsh', '-c', uri, 'domblklist', name, '--details'], timeout=10)
    disks = []
    for line in r2.stdout.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 4 and parts[1] == 'disk':
            disks.append(parts[3])
    info['Disks'] = ', '.join(disks) or '-'

    # Network info
    r3 = run_cmd(['virsh', '-c', uri, 'domiflist', name], timeout=10)
    ifaces = []
    for line in r3.stdout.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 5:
            ifaces.append(f"{parts[0]}({parts[2]})")
    info['Interfaces'] = ', '.join(ifaces) or '-'

    state = info.get('State', 'unknown').lower()
    info['Status'] = 'OK' if state == 'running' else ('WARN' if state == 'paused' else 'INFO')
    return info


def main():
    parser = make_base_parser('List all KVM guest VMs with state and resource info')
    parser.add_argument('--running', action='store_true', help='Show only running VMs')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    require_command('virsh', 'dnf install libvirt-client')

    uri = cfg.libvirt_uri
    names, err = get_vm_list(uri)

    rows = []
    for name in names:
        info = get_vm_info(name, uri)
        if args.running and info.get('State', '').lower() != 'running':
            continue
        rows.append({
            'VM Name':   info.get('Name',      ''),
            'State':     info.get('State',     ''),
            'vCPUs':     info.get('vCPUs',     ''),
            'RAM':       info.get('RAM',       ''),
            'Autostart': info.get('Autostart', ''),
            'Interfaces':info.get('Interfaces',''),
            'Status':    info.get('Status',    'INFO'),
        })

    overall = 'ok' if rows else 'warn'

    if args.json:
        out = ToolOutput(
            tool='kvm-vm-list',
            status=overall,
            summary=f"{len(rows)} VMs — {sum(1 for r in rows if r['State']=='running')} running",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('KVM Virtual Machine Inventory')
    print(f"  Hypervisor: {uri}   Total VMs: {len(rows)}\n")
    print_table(rows, columns=['VM Name', 'State', 'vCPUs', 'RAM', 'Autostart', 'Interfaces', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
