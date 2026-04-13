#!/usr/bin/env python3
"""
tools/system/software-inventory.py — Installed RPM package inventory.

Lists installed packages with version, architecture, install date, and vendor.
Supports filtering by recency, search term, and repository.

Usage:
    python3 tools/system/software-inventory.py
    python3 tools/system/software-inventory.py --recent 7
    python3 tools/system/software-inventory.py --search kernel
    python3 tools/system/software-inventory.py --vendor 'Rocky'
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        run_cmd, require_command, C, print_info, print_warn)


QUERYFORMAT = '|'.join([
    '%{NAME}',
    '%{VERSION}-%{RELEASE}',
    '%{ARCH}',
    '%{INSTALLTIME}',      # Unix timestamp
    '%{VENDOR}',
    '%{FROM_REPO}',
    '%{SIZE}',
])


def _format_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f'{n/1_000_000_000:.1f} GB'
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f} MB'
    if n >= 1_000:
        return f'{n/1_000:.1f} KB'
    return f'{n} B'


def _ts_to_date(ts_str: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromtimestamp(int(ts_str))
    except (ValueError, OSError):
        return None


def get_packages() -> list:
    result = run_cmd(
        ['rpm', '-qa', f'--queryformat=%{{INSTALLTIME}}|{QUERYFORMAT}\n'],
        timeout=60,
    )
    if result.returncode != 0:
        return []

    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('('):
            continue
        parts = line.split('|')
        if len(parts) < 7:
            continue

        ts_str, name, version, arch, installtime_dup, vendor, from_repo, size_str = \
            parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7] if len(parts) > 7 else '0'

        dt = _ts_to_date(ts_str)
        try:
            size = int(size_str)
        except ValueError:
            size = 0

        packages.append({
            'name':       name,
            'version':    version,
            'arch':       arch,
            'installed':  dt,
            'install_str': dt.strftime('%Y-%m-%d') if dt else '—',
            'vendor':     vendor or '—',
            'repo':       from_repo or '—',
            'size':       size,
            'size_str':   _format_size(size),
        })

    return sorted(packages, key=lambda p: p['installed'] or datetime.datetime.min, reverse=True)


def main():
    parser = make_base_parser('Installed RPM package inventory')
    parser.add_argument('--recent', metavar='DAYS', type=int, default=None,
                        help='Show only packages installed in the last N days')
    parser.add_argument('--search', metavar='TERM', default=None,
                        help='Filter package names containing TERM (case-insensitive)')
    parser.add_argument('--vendor', metavar='VENDOR', default=None,
                        help='Filter by vendor string (case-insensitive substring)')
    parser.add_argument('--repo', metavar='REPO', default=None,
                        help='Filter by repository ID (case-insensitive substring)')
    parser.add_argument('--sort', choices=('name', 'date', 'size'), default='date',
                        help='Sort order (default: date — newest first)')
    parser.add_argument('--top', metavar='N', type=int, default=None,
                        help='Show top N packages after filtering')
    args = parser.parse_args()
    apply_base_args(args)

    require_command('rpm', 'rpm package is part of the base system')

    packages = get_packages()

    # ── Apply filters ──────────────────────────────────────────────────────────
    cutoff = None
    if args.recent:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=args.recent)
        packages = [p for p in packages
                    if p['installed'] and p['installed'] >= cutoff]

    if args.search:
        term = args.search.lower()
        packages = [p for p in packages if term in p['name'].lower()]

    if args.vendor:
        term = args.vendor.lower()
        packages = [p for p in packages if term in p['vendor'].lower()]

    if args.repo:
        term = args.repo.lower()
        packages = [p for p in packages if term in p['repo'].lower()]

    # ── Sort ───────────────────────────────────────────────────────────────────
    if args.sort == 'name':
        packages.sort(key=lambda p: p['name'].lower())
    elif args.sort == 'size':
        packages.sort(key=lambda p: p['size'], reverse=True)
    # 'date' is already sorted newest-first from get_packages()

    if args.top:
        packages = packages[:args.top]

    # ── Build display records ──────────────────────────────────────────────────
    total_size  = sum(p['size'] for p in packages)
    records = [
        {
            'Package':   p['name'],
            'Version':   p['version'],
            'Arch':      p['arch'],
            'Installed': p['install_str'],
            'Repo':      p['repo'],
            'Size':      p['size_str'],
            'Status':    'OK',
        }
        for p in packages
    ]

    summary = (
        f'{len(packages):,} packages'
        + (f'  |  Installed in last {args.recent}d' if args.recent else '')
        + (f'  |  Search: {args.search}' if args.search else '')
        + f'  |  Total size: {_format_size(total_size)}'
    )

    if args.json:
        emit_json(ToolOutput(
            tool='software-inventory',
            status='ok',
            summary=summary,
            records=records,
        ))

    subtitle = f'{len(packages):,} packages  |  {_format_size(total_size)} total'
    if args.recent:
        subtitle += f'  |  Installed in last {args.recent} days'
    print_header('Software Inventory', subtitle)

    if not records:
        print_info('No packages match the specified filters.')
        sys.exit(0)

    print_table(records, ['Package', 'Version', 'Arch', 'Installed', 'Repo', 'Size', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
