#!/usr/bin/env python3
"""
tools/system/password-hash.py — Password hashing utility.

Generates password hashes in formats used by /etc/shadow, htpasswd, and
other common authentication systems. All hashing is done locally via
OpenSSL or Python's hashlib — no password is sent anywhere.

Usage:
    python3 tools/system/password-hash.py --password 'MySecret'
    python3 tools/system/password-hash.py --format sha512crypt
    echo 'MySecret' | python3 tools/system/password-hash.py --stdin
"""

import hashlib
import os
import secrets
import string
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        run_cmd, C, print_ok, print_warn, print_info, print_error)


FORMATS = ('sha512crypt', 'sha256crypt', 'md5crypt', 'htpasswd-apr1',
           'sha256', 'sha512', 'sha1', 'md5', 'all')


def _openssl_passwd(password: str, method: str) -> str:
    """Use openssl passwd for crypt-compatible hashes."""
    result = run_cmd(['openssl', 'passwd', method, '--stdin'],
                     input_text=password, timeout=10)
    if result.returncode != 0:
        return f'ERROR: {result.stderr.strip()}'
    return result.stdout.strip()


def hash_sha512crypt(password: str) -> str:
    return _openssl_passwd(password, '-6')


def hash_sha256crypt(password: str) -> str:
    return _openssl_passwd(password, '-5')


def hash_md5crypt(password: str) -> str:
    return _openssl_passwd(password, '-1')


def hash_htpasswd_apr1(password: str) -> str:
    return _openssl_passwd(password, '-apr1')


def hash_sha256(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def hash_sha512(password: str) -> str:
    return hashlib.sha512(password.encode()).hexdigest()


def hash_sha1(password: str) -> str:
    return hashlib.sha1(password.encode()).hexdigest()


def hash_md5(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


HASH_FUNCS = {
    'sha512crypt':   (hash_sha512crypt,  '/etc/shadow  (SHA-512 crypt — recommended for Linux)'),
    'sha256crypt':   (hash_sha256crypt,  '/etc/shadow  (SHA-256 crypt)'),
    'md5crypt':      (hash_md5crypt,     '/etc/shadow  (MD5 crypt — legacy)'),
    'htpasswd-apr1': (hash_htpasswd_apr1,'htpasswd / Apache .htpasswd (APR1-MD5)'),
    'sha256':        (hash_sha256,       'Hex digest — NOT a crypt hash, no salt'),
    'sha512':        (hash_sha512,       'Hex digest — NOT a crypt hash, no salt'),
    'sha1':          (hash_sha1,         'Hex digest — weak, avoid for new systems'),
    'md5':           (hash_md5,          'Hex digest — weak, avoid for new systems'),
}


def _check_openssl():
    r = run_cmd(['openssl', 'version'], timeout=5)
    return r.returncode == 0


def main():
    parser = make_base_parser('Password hashing utility — generate hashes for shadow, htpasswd, etc.')
    parser.add_argument('--password', '-p', default=None,
                        help='Password to hash (prompt if omitted; avoid shell history)')
    parser.add_argument('--stdin', action='store_true',
                        help='Read password from stdin (one line)')
    parser.add_argument('--format', '-f', default='all', choices=FORMATS,
                        help='Hash format to generate (default: all)')
    args = parser.parse_args()
    apply_base_args(args)

    # ── Get password ───────────────────────────────────────────────────────────
    if args.stdin:
        password = sys.stdin.readline().rstrip('\n')
    elif args.password:
        password = args.password
    else:
        import getpass
        try:
            password = getpass.getpass('Password: ')
            confirm  = getpass.getpass('Confirm:  ')
            if password != confirm:
                print_error('Passwords do not match.')
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)

    if not password:
        print_error('Password cannot be empty.')
        sys.exit(1)

    has_openssl = _check_openssl()
    if not has_openssl:
        print_warn('openssl not found — crypt formats will be unavailable')

    # ── Compute hashes ─────────────────────────────────────────────────────────
    formats_to_run = list(HASH_FUNCS.keys()) if args.format == 'all' else [args.format]
    records = []

    for fmt in formats_to_run:
        fn, use_case = HASH_FUNCS[fmt]
        needs_openssl = fmt in ('sha512crypt', 'sha256crypt', 'md5crypt', 'htpasswd-apr1')
        if needs_openssl and not has_openssl:
            result = 'SKIPPED (openssl not available)'
            status = 'WARN'
        else:
            result = fn(password)
            status = 'ERROR' if result.startswith('ERROR:') else 'OK'
        records.append({
            'Format':   fmt,
            'Hash':     result,
            'Use Case': use_case,
            'Status':   status,
        })

    # ── Output ─────────────────────────────────────────────────────────────────
    if args.json:
        emit_json(ToolOutput(
            tool='password-hash',
            status='ok',
            summary=f'{len(records)} format(s) generated',
            records=records,
        ))

    print_header('Password Hasher', 'Hashes generated locally — password not transmitted')
    print_warn('Do not pass passwords as --password on shared systems (visible in process list)')
    print_warn('Prefer: echo password | --stdin  or omit --password to use interactive prompt')
    print()
    print_table(records, ['Format', 'Hash', 'Use Case', 'Status'], status_col='Status')

    if args.format != 'all':
        # Print just the hash for easy copy/paste
        match = [r for r in records if r['Format'] == args.format]
        if match and match[0]['Status'] == 'OK':
            print_section('Result  (ready to paste)')
            print(match[0]['Hash'])


if __name__ == '__main__':
    main()
