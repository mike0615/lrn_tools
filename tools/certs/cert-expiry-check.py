#!/usr/bin/env python3
"""Cert Expiry Check — focused alerter; exit code reflects severity (0/2/1)."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_table, run_cmd, emit_json, ToolOutput,
                         print_ok, print_warn, print_crit)
from lib.config import load_config

# Reuse cert-inventory logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from cert_inventory_lib import find_certs, parse_cert  # type: ignore

# Inline the needed functions to keep this self-contained
import glob, datetime, re


def _find_certs(paths):
    found = set()
    for base in paths:
        base = os.path.expanduser(base)
        if os.path.isfile(base):
            found.add(base)
        elif os.path.isdir(base):
            for ext in ('*.pem', '*.crt', '*.cer'):
                for f in glob.glob(os.path.join(base, '**', ext), recursive=True):
                    found.add(f)
    return sorted(found)


def _parse_days(path):
    r = run_cmd(['openssl', 'x509', '-in', path, '-noout', '-enddate'], timeout=10)
    if r.returncode != 0:
        return None, 'parse error'
    for line in r.stdout.splitlines():
        if line.startswith('notAfter='):
            date_str = line.split('=', 1)[1].strip()
            try:
                exp = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                exp = exp.replace(tzinfo=datetime.timezone.utc)
                days = (exp - datetime.datetime.now(datetime.timezone.utc)).days
                return days, date_str
            except Exception:
                return None, date_str
    return None, 'unknown'


def main():
    parser = make_base_parser(
        'Check certificate expiry and alert on approaching deadlines',
        epilog='Exit codes: 0=all OK, 2=WARN, 1=CRITICAL'
    )
    parser.add_argument('--days', type=int, default=None,
                        help='Warning threshold in days (overrides config)')
    parser.add_argument('--path', action='append', metavar='PATH',
                        help='Additional path to scan')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    warn_days = args.days if args.days is not None else cfg.cert_warn_days
    crit_days = cfg.cert_critical_days

    scan_paths = cfg.cert_scan_paths
    if args.path:
        scan_paths += args.path
    if not scan_paths:
        scan_paths = ['/etc/pki/tls/certs', '/etc/ipa']

    cert_files = _find_certs(scan_paths)
    rows = []
    has_crit = False
    has_warn = False

    for path in cert_files:
        days, date_str = _parse_days(path)
        if days is None:
            continue
        if days <= crit_days:
            status = 'CRIT'
            has_crit = True
        elif days <= warn_days:
            status = 'WARN'
            has_warn = True
        else:
            continue  # OK — skip in expiry-focused report

        rows.append({
            'File':      path,
            'Expires':   date_str,
            'Days Left': str(days),
            'Status':    status,
        })

    overall = 'error' if has_crit else ('warn' if has_warn else 'ok')

    if args.json:
        out = ToolOutput(
            tool='cert-expiry-check',
            status=overall,
            summary=(f"{len(rows)} cert(s) need attention" if rows else
                     f"All certificates OK (checked {len(cert_files)})"),
            records=rows,
        )
        emit_json(out)

    print_header('Certificate Expiry Check')
    if not rows:
        print_ok(f"All {len(cert_files)} certificate(s) expire in more than {warn_days} days.\n")
    else:
        print_table(rows, columns=['File', 'Expires', 'Days Left', 'Status'], status_col='Status')

    sys.exit(1 if has_crit else (2 if has_warn else 0))


if __name__ == '__main__':
    main()
