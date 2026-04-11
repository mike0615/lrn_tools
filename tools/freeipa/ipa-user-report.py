#!/usr/bin/env python3
"""IPA User Report — list users with lock status, password expiry, groups."""

import os, sys, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


def parse_ipa_output(text):
    """Parse `ipa user-find --all` multi-record output into list of dicts."""
    records = []
    current = {}
    for line in text.splitlines():
        if line.startswith('---'):
            if current:
                records.append(current)
            current = {}
            continue
        if ':' in line and not line.startswith(' '):
            key, _, val = line.partition(':')
            current[key.strip()] = val.strip()
        elif line.startswith('  ') and records or current:
            # Continuation value
            pass
    if current:
        records.append(current)
    return records


def get_users():
    r = run_cmd(['ipa', 'user-find', '--all', '--sizelimit=0'], timeout=30)
    if r.returncode != 0:
        return [], r.stderr

    users = []
    blocks = r.stdout.split('  User login:')
    for block in blocks[1:]:  # skip header
        lines = block.splitlines()
        user = {}
        user['uid'] = lines[0].strip() if lines else ''
        for line in lines[1:]:
            if ':' in line:
                k, _, v = line.partition(':')
                k = k.strip()
                v = v.strip()
                if k and k not in user:
                    user[k] = v
        users.append(user)
    return users, ''


def main():
    parser = make_base_parser('List FreeIPA users with account status and password expiry')
    parser.add_argument('--locked',   action='store_true', help='Show only locked accounts')
    parser.add_argument('--expiring', action='store_true', help='Show only accounts with expiring passwords (< 30 days)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    users, err = get_users()

    rows = []
    for u in users:
        locked = u.get('Account disabled', 'FALSE').upper() == 'TRUE'
        if args.locked and not locked:
            continue

        row = {
            'UID':         u.get('uid', ''),
            'Full Name':   u.get('First name', '') + ' ' + u.get('Last name', ''),
            'Email':       u.get('Email address', ''),
            'Locked':      'YES' if locked else 'no',
            'Pwd Expires': u.get('Password expiration date', u.get('Kerberos password expiration', 'never')),
            'Last Login':  u.get('Last successful authentication', 'unknown'),
            'Status':      'WARN' if locked else 'OK',
        }
        rows.append(row)

    if not rows:
        rows = [{'UID': '(no users found or IPA not accessible)', 'Full Name': '',
                 'Email': '', 'Locked': '', 'Pwd Expires': '', 'Last Login': '', 'Status': 'WARN'}]

    overall = 'warn' if any(r['Status'] == 'WARN' for r in rows) else 'ok'

    if args.json:
        out = ToolOutput(
            tool='ipa-user-report',
            status=overall,
            summary=f"{len(rows)} users — {sum(1 for r in rows if r['Locked']=='YES')} locked",
            records=rows,
            errors=[err] if err else [],
        )
        emit_json(out)

    print_header('FreeIPA User Report')
    locked_count = sum(1 for r in rows if r['Locked'] == 'YES')
    print(f"  Total users: {len(rows)}   Locked: {locked_count}\n")
    print_table(rows, columns=['UID', 'Full Name', 'Email', 'Locked', 'Pwd Expires', 'Status'],
                status_col='Status')


if __name__ == '__main__':
    main()
