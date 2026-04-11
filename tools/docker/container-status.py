#!/usr/bin/env python3
"""Docker Container Status — list containers with image, state, ports, restarts."""

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput, require_command)
from lib.config import load_config


def get_containers(running_only=False):
    require_command('docker', 'dnf install docker-ce  # or podman-docker')

    fmt = ('{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}",'
           '"status":"{{.Status}}","state":"{{.State}}","ports":"{{.Ports}}",'
           '"restarts":"{{.RunningFor}}","created":"{{.CreatedAt}}"}')
    cmd = ['docker', 'ps', '--format', fmt]
    if not running_only:
        cmd.append('--all')

    r = run_cmd(cmd, timeout=15)
    if r.returncode != 0:
        return [], r.stderr

    containers = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
            containers.append(c)
        except json.JSONDecodeError:
            pass

    # Fallback: tabular parse if JSON format unavailable
    if not containers and r.stdout:
        cmd2 = ['docker', 'ps', '--all', '--no-trunc']
        if running_only:
            cmd2 = ['docker', 'ps', '--no-trunc']
        r2 = run_cmd(cmd2, timeout=15)
        for line in r2.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                containers.append({
                    'id': parts[0][:12], 'image': parts[1],
                    'state': 'running', 'name': parts[-1],
                    'ports': '', 'status': line, 'restarts': '', 'created': '',
                })
    return containers, ''


def get_images():
    r = run_cmd(['docker', 'images', '--format',
                 '{{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}'], timeout=15)
    rows = []
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            parts = line.split('\t')
            if len(parts) >= 2:
                rows.append({'Image': parts[0], 'Size': parts[1],
                             'Created': parts[2] if len(parts) > 2 else ''})
    return rows


def main():
    parser = make_base_parser('List Docker containers with state, ports, and resource info')
    parser.add_argument('--running', action='store_true', help='Show only running containers')
    args = parser.parse_args()
    apply_base_args(args)

    containers, err = get_containers(args.running)
    images          = get_images()

    cont_rows = []
    for c in containers:
        state  = c.get('state', c.get('status', 'unknown')).lower()
        status = 'OK' if state == 'running' else ('WARN' if state in ('paused', 'restarting') else 'INFO')
        ports  = c.get('ports', '')[:40] or '-'
        cont_rows.append({
            'Name':    c.get('name', ''),
            'Image':   c.get('image', '')[:35],
            'State':   state,
            'Ports':   ports,
            'Created': c.get('created', ''),
            'Status':  status,
        })

    img_rows = [{'Image': i['Image'][:50], 'Size': i['Size'], 'Created': i['Created']}
                for i in images]

    overall = ('error' if any(r['Status']=='FAIL' for r in cont_rows) else
               'warn'  if any(r['Status']=='WARN' for r in cont_rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='docker-container-status',
            status=overall,
            summary=f"{len(containers)} containers — {sum(1 for r in cont_rows if r['State']=='running')} running",
            records=[{'section': 'containers', **r} for r in cont_rows] +
                    [{'section': 'images',     **r} for r in img_rows],
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('Docker Container Status')
    from lib.common import print_section
    print_section(f'Containers ({len(cont_rows)} total)')
    if cont_rows:
        print_table(cont_rows, columns=['Name', 'Image', 'State', 'Ports', 'Created', 'Status'],
                    status_col='Status')
    else:
        print('  No containers found.\n')

    print_section(f'Images ({len(img_rows)} total)')
    if img_rows:
        print_table(img_rows, columns=['Image', 'Size', 'Created'])


if __name__ == '__main__':
    main()
