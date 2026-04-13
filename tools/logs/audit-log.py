#!/usr/bin/env python3
"""
tools/logs/audit-log.py — Audit log collector and event viewer.

Queries the Linux audit subsystem via ausearch/aureport, or reads
/var/log/audit/audit.log directly if audit tools are unavailable.
Requires root or membership in the 'adm' group for log access.

Usage:
    python3 tools/logs/audit-log.py
    python3 tools/logs/audit-log.py --type USER_AUTH --hours 48
    python3 tools/logs/audit-log.py --summary
    python3 tools/logs/audit-log.py --user admin
"""

import os
import re
import sys
import shutil
import subprocess
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        run_cmd, C, print_ok, print_warn, print_info,
                        print_error, status_badge)


AUDIT_LOG = '/var/log/audit/audit.log'

# Interesting event types and their descriptions
EVENT_TYPES = {
    'USER_AUTH':    'Authentication attempt',
    'USER_ACCT':    'User account check',
    'USER_LOGIN':   'User login',
    'USER_LOGOUT':  'User logout',
    'USER_CMD':     'User command (sudo)',
    'USER_START':   'User session start',
    'USER_END':     'User session end',
    'SYSCALL':      'System call',
    'EXECVE':       'Process execution',
    'PATH':         'File path access',
    'AVC':          'SELinux AVC denial',
    'SELINUX_ERR':  'SELinux error',
    'USER_ROLE_CHANGE': 'SELinux role change',
    'ADD_USER':     'User account added',
    'DEL_USER':     'User account deleted',
    'ADD_GROUP':    'Group added',
    'DEL_GROUP':    'Group deleted',
    'CHGRP_ID':     'Group ID change',
    'CHUSER_ID':    'User ID change',
    'CRED_REFR':    'Credential refresh',
    'CRED_ACQ':     'Credential acquired',
    'CRED_DISP':    'Credential disposed',
    'LOGIN':        'Login session',
    'CRYPTO_KEY_USER': 'Cryptographic key use',
    'CONFIG_CHANGE':'Configuration changed',
    'DAEMON_START': 'Audit daemon start',
    'DAEMON_END':   'Audit daemon stop',
}


def _since_ts(hours: int) -> int:
    """Return Unix timestamp for N hours ago."""
    return int((datetime.datetime.now() - datetime.timedelta(hours=hours)).timestamp())


def ausearch_events(hours: int, event_type: str, username: str) -> list:
    """Query audit log via ausearch."""
    since = datetime.datetime.now() - datetime.timedelta(hours=hours)
    since_str = since.strftime('%m/%d/%Y %H:%M:%S')

    cmd = ['ausearch', '--start', since_str, '--interpret', '-i']
    if event_type and event_type.lower() != 'all':
        cmd += ['--message', event_type]
    if username:
        cmd += ['--user', username]

    result = run_cmd(cmd, timeout=30)
    if result.returncode not in (0, 1):
        return None  # ausearch failed — caller tries fallback

    events = []
    current = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith('----'):
            if current:
                events.append(current)
            current = {}
        elif line.startswith('type='):
            m = re.match(r'type=(\S+)\s+msg=audit\(([^)]+)\):\s*(.*)', line)
            if m:
                etype, ts_raw, body = m.group(1), m.group(2), m.group(3)
                try:
                    ts_unix = float(ts_raw.split(':')[0])
                    ts = datetime.datetime.fromtimestamp(ts_unix).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    ts = ts_raw
                current['Type']    = etype
                current['Time']    = ts
                # Extract key fields
                for field in ('user', 'auid', 'uid', 'exe', 'hostname', 'addr', 'res', 'op', 'acct'):
                    m2 = re.search(rf'\b{field}=(\S+)', body)
                    if m2:
                        current[field] = m2.group(1).strip("'\"")
                current['Raw'] = body[:120]
    if current:
        events.append(current)
    return events


def direct_parse(hours: int, event_type: str, username: str) -> list:
    """Parse /var/log/audit/audit.log directly as fallback."""
    if not os.path.exists(AUDIT_LOG):
        return []

    since_ts = _since_ts(hours)
    events   = []

    try:
        with open(AUDIT_LOG, errors='replace') as f:
            for line in f:
                m = re.match(r'type=(\S+)\s+msg=audit\((\d+\.\d+):\d+\):\s*(.*)', line)
                if not m:
                    continue
                etype, ts_raw, body = m.group(1), m.group(2), m.group(3)
                try:
                    ts_unix = float(ts_raw)
                except ValueError:
                    continue
                if ts_unix < since_ts:
                    continue
                if event_type and event_type.lower() != 'all' and etype != event_type:
                    continue
                if username:
                    if f'acct={username}' not in body and f'uid={username}' not in body:
                        continue

                ts = datetime.datetime.fromtimestamp(ts_unix).strftime('%Y-%m-%d %H:%M:%S')
                ev = {'Type': etype, 'Time': ts}
                for field in ('acct', 'exe', 'hostname', 'addr', 'res'):
                    m2 = re.search(rf'\b{field}=(\S+)', body)
                    if m2:
                        ev[field] = m2.group(1).strip('"')
                ev['Raw'] = body[:120]
                events.append(ev)
    except PermissionError:
        print_error(f'Permission denied: {AUDIT_LOG}  (run as root or add user to adm group)')
        sys.exit(1)

    return events


def aureport_summary(hours: int) -> list:
    """Generate summary report via aureport."""
    since = datetime.datetime.now() - datetime.timedelta(hours=hours)
    since_str = since.strftime('%m/%d/%Y %H:%M:%S')

    sections = []

    # Authentication report
    r = run_cmd(['aureport', '--start', since_str, '--auth', '--summary'], timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        sections.append(('Authentication Summary', r.stdout))

    # User account modifications
    r = run_cmd(['aureport', '--start', since_str, '--mods', '--summary'], timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        sections.append(('Modification Summary', r.stdout))

    # Executable report
    r = run_cmd(['aureport', '--start', since_str, '--executable', '--summary'], timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        sections.append(('Executable Summary', r.stdout))

    # SELinux AVC
    r = run_cmd(['aureport', '--start', since_str, '--avc', '--summary'], timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        sections.append(('SELinux AVC Summary', r.stdout))

    return sections


def build_records(events: list) -> list:
    """Convert parsed events to display records."""
    rows = []
    for ev in events:
        res = ev.get('res', '')
        status = 'OK' if res in ('success', 'yes', '1') else ('ERROR' if res in ('failed', 'no', '0') else 'INFO')
        rows.append({
            'Time':     ev.get('Time', ''),
            'Type':     ev.get('Type', ''),
            'Account':  ev.get('acct', ev.get('user', ev.get('auid', ''))),
            'Exe':      ev.get('exe', '').lstrip('(').rstrip(')'),
            'Host':     ev.get('hostname', ev.get('addr', '')),
            'Result':   res or '—',
            'Status':   status,
        })
    return rows


def main():
    parser = make_base_parser('Audit log collector and event viewer')
    parser.add_argument('--hours',   type=int, default=24,
                        help='Look back N hours (default: 24)')
    parser.add_argument('--type',    default='all',
                        help='Event type filter: USER_AUTH, USER_LOGIN, USER_CMD, AVC, etc. (default: all)')
    parser.add_argument('--user',    default=None,
                        help='Filter by username or UID')
    parser.add_argument('--summary', action='store_true',
                        help='Show summary report via aureport instead of individual events')
    parser.add_argument('--top',     type=int, default=200,
                        help='Maximum events to display (default: 200)')
    args = parser.parse_args()
    apply_base_args(args)

    has_ausearch = bool(shutil.which('ausearch'))
    has_aureport = bool(shutil.which('aureport'))

    # ── Summary mode ───────────────────────────────────────────────────────────
    if args.summary:
        if not has_aureport:
            print_error('aureport not found (dnf install audit)')
            sys.exit(1)
        sections = aureport_summary(args.hours)
        print_header('Audit Log Summary', f'Last {args.hours} hours')
        for title, text in sections:
            print_section(title)
            print(text)
        sys.exit(0)

    # ── Event collection ───────────────────────────────────────────────────────
    events = None
    method = 'ausearch'

    if has_ausearch:
        events = ausearch_events(args.hours, args.type, args.user)

    if events is None:
        method = 'direct'
        print_warn('ausearch not available — reading log directly')
        events = direct_parse(args.hours, args.type, args.user)

    events = events[-args.top:]  # cap display
    records = build_records(events)

    total     = len(records)
    failures  = sum(1 for r in records if r['Status'] == 'ERROR')
    status    = 'warn' if failures > 0 else 'ok'

    if args.json:
        emit_json(ToolOutput(
            tool='audit-log',
            status=status,
            summary=f'{total} events  |  {failures} failures  |  method: {method}',
            records=records,
        ))

    print_header('Audit Log', f'Last {args.hours} hours  |  {method}')
    print(f'  {C.DIM}Events:{C.RESET} {total}    '
          f'{C.RED}Failures:{C.RESET} {failures}\n')

    if not records:
        print_info('No audit events found for the specified criteria.')
        sys.exit(0)

    print_table(records, ['Time', 'Type', 'Account', 'Exe', 'Host', 'Result', 'Status'],
                status_col='Status')

    rc = 2 if failures > 0 else 0
    sys.exit(rc)


if __name__ == '__main__':
    main()
