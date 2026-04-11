#!/usr/bin/env python3
"""DNF Repo Health — check enabled repositories and test reachability."""

import os, sys, socket, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def parse_repos():
    r = run_cmd(['dnf', 'repolist', '--verbose', '--all'], timeout=60)
    if r.returncode != 0:
        return [], r.stderr

    repos = []
    current = {}
    for line in r.stdout.splitlines():
        if line.startswith('Repo-id'):
            if current:
                repos.append(current)
            current = {}
            current['id'] = line.split(':', 1)[1].strip()
        elif line.startswith('Repo-name'):
            current['name'] = line.split(':', 1)[1].strip()
        elif line.startswith('Repo-status'):
            current['status'] = line.split(':', 1)[1].strip()
        elif line.startswith('Repo-baseurl'):
            current['baseurl'] = line.split(':', 1)[1].strip().split()[0]
        elif line.startswith('Repo-pkgs'):
            current['pkgs'] = line.split(':', 1)[1].strip()
    if current:
        repos.append(current)
    return repos, ''


def test_url_reachable(url):
    """Try TCP connect to host:port from URL. Returns True/False."""
    try:
        m = re.match(r'https?://([^/:]+)(?::(\d+))?', url)
        if not m:
            return None  # local/file url
        host = m.group(1)
        port = int(m.group(2) or (443 if url.startswith('https') else 80))
        s = socket.create_connection((host, port), timeout=5)
        s.close()
        return True
    except Exception:
        return False


def main():
    parser = make_base_parser('Check enabled DNF repositories and test their reachability')
    args = parser.parse_args()
    apply_base_args(args)

    repos, err = parse_repos()
    rows = []

    for repo in repos:
        enabled = repo.get('status', '') == 'enabled'
        baseurl = repo.get('baseurl', '')
        reach   = None
        if enabled and baseurl:
            reach = test_url_reachable(baseurl)

        if reach is True:
            net_status = 'reachable'
        elif reach is False:
            net_status = 'unreachable'
        else:
            net_status = 'local/file'

        status = ('OK' if enabled and reach is not False else
                  ('WARN' if enabled and reach is False else 'INFO'))

        rows.append({
            'Repo ID':    repo.get('id', '')[:35],
            'Name':       repo.get('name', '')[:30],
            'Enabled':    'yes' if enabled else 'no',
            'Packages':   repo.get('pkgs', '?'),
            'Network':    net_status,
            'Status':     status,
        })

    overall = ('error' if any(r['Status'] == 'FAIL' for r in rows) else
               'warn'  if any(r['Status'] == 'WARN' for r in rows) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='dnf-repo-health',
            status=overall,
            summary=f"{sum(1 for r in rows if r['Enabled']=='yes')} repos enabled, "
                    f"{sum(1 for r in rows if r['Network']=='unreachable')} unreachable",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('DNF Repository Health')
    print_table(rows, columns=['Repo ID', 'Name', 'Enabled', 'Packages', 'Network', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
