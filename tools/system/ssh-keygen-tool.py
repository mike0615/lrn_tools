#!/usr/bin/env python3
"""
tools/system/ssh-keygen-tool.py — SSH key pair generator.

Generates SSH key pairs using the system ssh-keygen. Displays the public key,
fingerprint, and path so you can immediately copy and deploy the key.

Usage:
    python3 tools/system/ssh-keygen-tool.py --name myserver --type ed25519
    python3 tools/system/ssh-keygen-tool.py --type rsa --bits 4096
    python3 tools/system/ssh-keygen-tool.py --list
"""

import os
import sys
import subprocess
import glob
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.common import (make_base_parser, apply_base_args, print_header,
                        print_section, print_table, ToolOutput, emit_json,
                        run_cmd, require_command, C, print_ok, print_warn,
                        print_info, print_error)


SSH_DIR = os.path.expanduser('~/.ssh')

VALID_TYPES = ('ed25519', 'rsa', 'ecdsa', 'ecdsa-sk', 'ed25519-sk')


def list_keys(ssh_dir: str) -> list:
    """List existing key pairs in the SSH directory."""
    keys = []
    for pub in sorted(glob.glob(os.path.join(ssh_dir, '*.pub'))):
        priv = pub[:-4]
        exists = os.path.exists(priv)
        stat   = os.stat(pub)
        mtime  = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d')
        # Read first line of public key for type info
        try:
            with open(pub) as f:
                line = f.readline().strip()
            key_type = line.split()[0] if line else 'unknown'
            comment  = line.split()[-1] if len(line.split()) >= 3 else ''
        except Exception:
            key_type = 'unknown'
            comment  = ''
        keys.append({
            'Key File': os.path.basename(priv),
            'Type':     key_type,
            'Comment':  comment,
            'Private':  'YES' if exists else 'NO',
            'Created':  mtime,
            'Status':   'OK' if exists else 'WARN',
        })
    return keys


def generate_key(key_type: str, bits: int, key_path: str,
                 comment: str, passphrase: str) -> tuple:
    """
    Generate an SSH key pair. Returns (success, message, public_key_content).
    """
    cmd = ['ssh-keygen', '-t', key_type, '-f', key_path, '-C', comment, '-N', passphrase]
    if key_type == 'rsa' and bits:
        cmd += ['-b', str(bits)]
    if key_type == 'ecdsa':
        valid_bits = (256, 384, 521)
        if bits not in valid_bits:
            bits = 521
        cmd += ['-b', str(bits)]

    if os.path.exists(key_path):
        return False, f'Key already exists at {key_path}. Use --force to overwrite.', ''

    result = run_cmd(cmd, timeout=30)
    if result.returncode != 0:
        return False, result.stderr.strip() or 'ssh-keygen failed', ''

    pub_path = key_path + '.pub'
    try:
        pub_content = open(pub_path).read().strip()
    except Exception:
        pub_content = ''

    return True, f'Key pair generated at {key_path}', pub_content


def get_fingerprint(key_path: str) -> str:
    """Get fingerprint of a public key."""
    pub = key_path if key_path.endswith('.pub') else key_path + '.pub'
    result = run_cmd(['ssh-keygen', '-lf', pub], timeout=10)
    return result.stdout.strip() if result.returncode == 0 else 'N/A'


def main():
    parser = make_base_parser('SSH key pair generator')
    parser.add_argument('--type', default='ed25519', choices=list(VALID_TYPES),
                        help='Key type (default: ed25519)')
    parser.add_argument('--bits', type=int, default=None,
                        help='Key bits — RSA: 2048/4096 (default 4096), ECDSA: 256/384/521 (default 521)')
    parser.add_argument('--name', default=None,
                        help='Key filename without extension (default: id_<type>)')
    parser.add_argument('--dir', default=SSH_DIR, dest='key_dir',
                        help=f'Output directory (default: {SSH_DIR})')
    parser.add_argument('--comment', default=f'{os.getlogin()}@{os.uname().nodename}',
                        help='Key comment (default: user@host)')
    parser.add_argument('--passphrase', default='',
                        help='Key passphrase (default: none — empty passphrase)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing key')
    parser.add_argument('--list', action='store_true',
                        help='List existing keys in the SSH directory')
    args = parser.parse_args()
    apply_base_args(args)

    require_command('ssh-keygen', 'dnf install openssh-clients')
    os.makedirs(args.key_dir, mode=0o700, exist_ok=True)

    # ── List mode ──────────────────────────────────────────────────────────────
    if args.list:
        keys = list_keys(args.key_dir)
        if args.json:
            emit_json(ToolOutput(
                tool='ssh-keygen-tool',
                status='ok',
                summary=f'{len(keys)} key(s) found in {args.key_dir}',
                records=keys,
            ))
        print_header('SSH Keys', args.key_dir)
        if not keys:
            print_info(f'No key pairs found in {args.key_dir}')
        else:
            print_table(keys, ['Key File', 'Type', 'Comment', 'Private', 'Created', 'Status'],
                        status_col='Status')
        sys.exit(0)

    # ── Generate mode ──────────────────────────────────────────────────────────
    key_name = args.name or f'id_{args.key_type}'
    key_path = os.path.join(args.key_dir, key_name)

    # Handle --force
    if args.force and os.path.exists(key_path):
        os.remove(key_path)
        if os.path.exists(key_path + '.pub'):
            os.remove(key_path + '.pub')

    bits = args.bits
    if args.key_type == 'rsa' and not bits:
        bits = 4096
    if args.key_type == 'ecdsa' and not bits:
        bits = 521

    success, message, pub_content = generate_key(
        args.key_type, bits, key_path, args.comment, args.passphrase
    )

    if not success:
        print_error(message)
        if args.json:
            emit_json(ToolOutput(tool='ssh-keygen-tool', status='error',
                                 summary=message, records=[], errors=[message]))
        sys.exit(1)

    fingerprint = get_fingerprint(key_path)

    records = [
        {'Field': 'Private Key',   'Value': key_path,        'Status': 'OK'},
        {'Field': 'Public Key',    'Value': key_path + '.pub','Status': 'OK'},
        {'Field': 'Key Type',      'Value': args.key_type,    'Status': 'OK'},
        {'Field': 'Fingerprint',   'Value': fingerprint,      'Status': 'OK'},
        {'Field': 'Comment',       'Value': args.comment,     'Status': 'OK'},
        {'Field': 'Passphrase',    'Value': 'Set' if args.passphrase else 'None (no passphrase)', 'Status': 'INFO'},
    ]

    if args.json:
        emit_json(ToolOutput(
            tool='ssh-keygen-tool',
            status='ok',
            summary=message,
            records=records + [{'Field': 'Public Key Content', 'Value': pub_content, 'Status': 'OK'}],
        ))

    print_header('SSH Key Generator', f'{args.key_type.upper()} key pair')
    print_ok(message)
    print()
    print_table(records, ['Field', 'Value', 'Status'], status_col='Status')

    print_section('Public Key  (copy to remote ~/.ssh/authorized_keys)')
    print(f'{C.DIM}{pub_content}{C.RESET}')
    print()
    print_section('Quick Deploy')
    print(f'{C.DIM}ssh-copy-id -i {key_path}.pub user@remote-host{C.RESET}')
    print(f'{C.DIM}# or manually:{C.RESET}')
    print(f'{C.DIM}cat {key_path}.pub | ssh user@remote-host "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"{C.RESET}')


if __name__ == '__main__':
    main()
