#!/usr/bin/env python3
"""Certificate Inventory — scan paths for PEM certs, report subject/SAN/expiry."""

import os, sys, glob, datetime, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def parse_cert(path):
    """Use openssl to extract cert fields. Returns dict or None on failure."""
    r = run_cmd(['openssl', 'x509', '-in', path, '-noout',
                 '-subject', '-issuer', '-enddate', '-startdate', '-ext', 'subjectAltName'],
                timeout=10)
    if r.returncode != 0:
        # Try DER format
        r = run_cmd(['openssl', 'x509', '-in', path, '-inform', 'DER', '-noout',
                     '-subject', '-issuer', '-enddate', '-startdate'],
                    timeout=10)
        if r.returncode != 0:
            return None

    info = {'path': path}
    san_lines = []
    in_san = False
    for line in r.stdout.splitlines():
        if line.startswith('subject='):
            info['subject'] = line.split('=', 1)[1].strip()
        elif line.startswith('issuer='):
            info['issuer'] = line.split('=', 1)[1].strip()
        elif line.startswith('notAfter='):
            info['not_after'] = line.split('=', 1)[1].strip()
        elif line.startswith('notBefore='):
            info['not_before'] = line.split('=', 1)[1].strip()
        elif 'X509v3 Subject Alternative Name' in line:
            in_san = True
        elif in_san and line.strip():
            san_lines.append(line.strip())
            in_san = False

    info['san'] = san_lines[0] if san_lines else ''

    # Calculate days to expiry
    if 'not_after' in info:
        try:
            # notAfter format: "Jan  1 00:00:00 2026 GMT"
            exp = datetime.datetime.strptime(info['not_after'], '%b %d %H:%M:%S %Y %Z')
            exp = exp.replace(tzinfo=datetime.timezone.utc)
            days = (exp - datetime.datetime.now(datetime.timezone.utc)).days
            info['days_left'] = days
        except Exception:
            info['days_left'] = None
    return info


def find_certs(paths):
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


def main():
    parser = make_base_parser('Scan configured paths for PEM certificates and report details')
    parser.add_argument('--path', action='append', metavar='PATH',
                        help='Additional path to scan (file or directory)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    scan_paths = cfg.cert_scan_paths
    if args.path:
        scan_paths += args.path

    if not scan_paths:
        scan_paths = ['/etc/pki/tls/certs', '/etc/ipa']

    cert_files = find_certs(scan_paths)
    rows = []
    errors = []

    warn_days = cfg.cert_warn_days
    crit_days = cfg.cert_critical_days

    for path in cert_files:
        info = parse_cert(path)
        if info is None:
            errors.append(f"Could not parse: {path}")
            continue

        days = info.get('days_left')
        if days is None:
            status = 'WARN'
        elif days <= crit_days:
            status = 'CRIT'
        elif days <= warn_days:
            status = 'WARN'
        else:
            status = 'OK'

        # Shorten CN from subject
        cn_match = re.search(r'CN\s*=\s*([^,/]+)', info.get('subject', ''))
        cn = cn_match.group(1).strip() if cn_match else info.get('subject', '')[:40]

        rows.append({
            'File':      os.path.basename(path),
            'CN':        cn[:35],
            'Expires':   info.get('not_after', 'unknown'),
            'Days Left': str(days) if days is not None else '?',
            'Status':    status,
        })

    overall = ('error' if any(r['Status'] == 'CRIT' for r in rows) else
               'warn'  if any(r['Status'] == 'WARN' for r in rows) else 'ok')

    if not rows:
        rows = [{'File': '(no certificates found)', 'CN': '', 'Expires': '',
                 'Days Left': '', 'Status': 'WARN'}]
        overall = 'warn'

    if args.json:
        out = ToolOutput(
            tool='cert-inventory',
            status=overall,
            summary=f"{len(rows)} certificates — {sum(1 for r in rows if r['Status']!='OK')} need attention",
            records=rows,
            errors=errors,
        )
        emit_json(out)

    print_header('Certificate Inventory')
    print(f"  Scanned {len(cert_files)} certificate files in {len(scan_paths)} path(s)\n")
    print_table(rows, columns=['File', 'CN', 'Expires', 'Days Left', 'Status'], status_col='Status')
    if errors:
        print_section('Parse Errors')
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    main()
