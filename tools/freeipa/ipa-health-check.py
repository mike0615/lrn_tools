#!/usr/bin/env python3
"""IPA Health Check — services, replication, CA, and cert status."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config, ConfigError


def check_ipa_services():
    rows = []
    r = run_cmd(['ipactl', 'status'], timeout=20)
    if r.returncode not in (0, 1):
        return [{'Service': 'ipactl', 'Status': 'ERROR', 'Detail': r.stderr or 'ipactl not found'}]

    for line in r.stdout.splitlines():
        if ' is ' in line.lower():
            parts = line.rsplit(' is ', 1)
            name = parts[0].strip()
            state = parts[1].strip().rstrip('.')
            status = 'OK' if state.lower() in ('running', 'active') else 'FAIL'
            rows.append({'Service': name, 'State': state, 'Status': status})
    return rows


def check_replication():
    rows = []
    r = run_cmd(['ipa-replica-manage', 'list', '--verbose'], timeout=15)
    if r.returncode != 0:
        # Try without --verbose
        r = run_cmd(['ipa-replica-manage', 'list'], timeout=15)
    if r.returncode != 0:
        return [{'Replica': 'N/A', 'Status': 'WARN', 'Detail': 'Could not query replication (no IPA ticket?)'}]

    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        host, _, state = line.partition(':')
        state = state.strip()
        status = 'OK' if 'master' in state.lower() or 'replica' in state.lower() else 'WARN'
        rows.append({'Replica': host.strip(), 'Role': state, 'Status': status})
    return rows or [{'Replica': 'none', 'Role': 'standalone', 'Status': 'OK'}]


def check_ipa_certs():
    rows = []
    r = run_cmd(['ipa', 'cert-find', '--certificate-out=/dev/null', '--sizelimit=0'],
                timeout=15)
    # More practical: check the IPA CA cert expiry directly
    ca_cert = '/etc/ipa/ca.crt'
    if os.path.isfile(ca_cert):
        r2 = run_cmd(['openssl', 'x509', '-in', ca_cert,
                      '-noout', '-subject', '-enddate'])
        if r2.returncode == 0:
            subject = ''
            end_date = ''
            for line in r2.stdout.splitlines():
                if line.startswith('subject='):
                    subject = line.split('=', 1)[1].strip()
                elif line.startswith('notAfter='):
                    end_date = line.split('=', 1)[1].strip()
            import datetime
            try:
                from email.utils import parsedate
                dt_tuple = parsedate(end_date)
                if dt_tuple:
                    expire_dt = datetime.datetime(*dt_tuple[:6],
                                                   tzinfo=datetime.timezone.utc)
                    days_left = (expire_dt - datetime.datetime.now(datetime.timezone.utc)).days
                    status = 'OK' if days_left > 30 else ('WARN' if days_left > 7 else 'CRIT')
                    rows.append({
                        'Cert':     'IPA CA',
                        'Subject':  subject[:50],
                        'Expires':  end_date,
                        'Days Left': str(days_left),
                        'Status':   status,
                    })
            except Exception:
                rows.append({'Cert': 'IPA CA', 'Subject': subject,
                             'Expires': end_date, 'Days Left': '?', 'Status': 'WARN'})
    if not rows:
        rows.append({'Cert': 'IPA CA', 'Subject': 'Not found', 'Expires': '-',
                     'Days Left': '-', 'Status': 'WARN'})
    return rows


def check_kerberos():
    r = run_cmd(['klist', '-s'])
    has_ticket = r.returncode == 0
    rows = [{'Check': 'Kerberos TGT', 'Status': 'OK' if has_ticket else 'WARN',
              'Detail': 'Valid TGT present' if has_ticket else 'No valid TGT — some checks may fail'}]
    return rows


def main():
    parser = make_base_parser('Check FreeIPA service health, replication, and certificate status')
    parser.add_argument('--server', help='IPA server hostname (overrides config)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    svc_rows   = check_ipa_services()
    krb_rows   = check_kerberos()
    repl_rows  = check_replication()
    cert_rows  = check_ipa_certs()

    all_statuses = [r.get('Status', 'OK') for rows in [svc_rows, repl_rows, cert_rows]
                    for r in rows]
    overall = ('error' if any(s in ('FAIL', 'CRIT', 'ERROR') for s in all_statuses) else
               'warn'  if any(s == 'WARN' for s in all_statuses) else 'ok')

    if args.json:
        out = ToolOutput(
            tool='ipa-health-check',
            status=overall,
            summary=f"IPA health: {sum(1 for s in all_statuses if s == 'OK')}/{len(all_statuses)} checks OK",
            records=[{**r, 'section': 'services'}    for r in svc_rows] +
                    [{**r, 'section': 'kerberos'}    for r in krb_rows] +
                    [{**r, 'section': 'replication'} for r in repl_rows] +
                    [{**r, 'section': 'certs'}       for r in cert_rows],
        )
        emit_json(out)

    print_header('FreeIPA Health Check')
    print_section('Kerberos')
    print_table(krb_rows, columns=['Check', 'Status', 'Detail'], status_col='Status')
    print_section('IPA Services (ipactl)')
    print_table(svc_rows, columns=['Service', 'State', 'Status'], status_col='Status')
    print_section('Replication')
    print_table(repl_rows, status_col='Status')
    print_section('CA Certificate')
    print_table(cert_rows, columns=['Cert', 'Subject', 'Expires', 'Days Left', 'Status'], status_col='Status')


if __name__ == '__main__':
    main()
