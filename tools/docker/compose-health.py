#!/usr/bin/env python3
"""Docker Compose Health — check service state across configured compose projects."""

import os, sys, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def find_compose_files(paths):
    found = []
    for base in paths:
        base = os.path.expanduser(base)
        for name in ('docker-compose.yml', 'docker-compose.yaml',
                     'compose.yml', 'compose.yaml'):
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                found.append((base, candidate))
                break
    return found


def check_project(project_dir, compose_file):
    rows = []
    project_name = os.path.basename(project_dir)

    r = run_cmd(['docker', 'compose', '-f', compose_file, 'ps',
                 '--format', 'json'], timeout=20)
    if r.returncode != 0:
        # Older docker-compose v1 fallback
        r = run_cmd(['docker-compose', '-f', compose_file, 'ps'], timeout=20)
        if r.returncode != 0:
            rows.append({'Project': project_name, 'Service': 'error',
                         'State': r.stderr[:50], 'Status': 'FAIL'})
            return rows

    # Try JSON parse (Docker Compose v2)
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            svc = json.loads(line)
            state = svc.get('State', svc.get('status', 'unknown')).lower()
            status = 'OK' if state == 'running' else 'WARN'
            rows.append({
                'Project': project_name,
                'Service': svc.get('Service', svc.get('Name', '')),
                'Image':   svc.get('Image', '')[:35],
                'State':   state,
                'Ports':   (svc.get('Publishers') or [{'TargetPort': '-'}])[0].get('TargetPort', '-')
                           if isinstance(svc.get('Publishers'), list) else '-',
                'Status':  status,
            })
        except json.JSONDecodeError:
            # Plain text fallback
            parts = line.split()
            if len(parts) >= 3:
                state = parts[2].lower()
                rows.append({'Project': project_name, 'Service': parts[0],
                             'Image': '-', 'State': state, 'Ports': '-',
                             'Status': 'OK' if 'up' in state else 'WARN'})
    return rows


def main():
    parser = make_base_parser('Check Docker Compose project service health')
    parser.add_argument('--path', help='Additional compose project directory', action='append')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    compose_paths = list(cfg.compose_paths)
    if args.path:
        compose_paths += args.path

    projects = find_compose_files(compose_paths)

    all_rows = []
    for proj_dir, compose_file in projects:
        rows = check_project(proj_dir, compose_file)
        all_rows.extend(rows)

    if not all_rows:
        if not compose_paths:
            msg = 'No compose paths configured. Set [docker] compose_paths in config.'
        else:
            msg = 'No docker-compose.yml files found in configured paths.'
        all_rows = [{'Project': msg, 'Service': '', 'Image': '',
                     'State': '', 'Ports': '', 'Status': 'WARN'}]

    overall = ('error' if any(r['Status']=='FAIL' for r in all_rows) else
               'warn'  if any(r['Status']=='WARN' for r in all_rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='docker-compose-health',
            status=overall,
            summary=f"{len(projects)} project(s), {len(all_rows)} service(s)",
            records=all_rows,
        )
        emit_json(out)

    print_header('Docker Compose Health')
    for proj_dir, _ in projects:
        print_section(os.path.basename(proj_dir))
        proj_rows = [r for r in all_rows if r['Project'] == os.path.basename(proj_dir)]
        print_table(proj_rows, columns=['Service', 'Image', 'State', 'Ports', 'Status'],
                    status_col='Status')

    if not projects:
        print('  No compose projects found.\n')


if __name__ == '__main__':
    main()
