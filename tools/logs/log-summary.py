#!/usr/bin/env python3
"""Log Summary — scan configured log files with regex patterns and report frequency."""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.common import (make_base_parser, apply_base_args, print_header,
                         print_section, print_table, run_cmd, emit_json, ToolOutput)
from lib.config import load_config


DEFAULT_PATTERNS = {
    'ERROR':        r'\bERROR\b|\berror\b',
    'WARNING':      r'\bWARN(ING)?\b',
    'CRITICAL':     r'\bCRITICAL\b|\bCRIT\b',
    'Auth Failure': r'authentication failure|Failed password|Invalid user',
    'Denied':       r'\bDENIED\b|\bdenied\b',
    'Segfault':     r'\bsegfault\b|\bsegmentation fault\b',
}

# Approximate line-timestamp patterns for --hours filtering
TS_PATTERNS = [
    re.compile(r'^(\w{3}\s+\d+\s+\d+:\d+:\d+)'),          # syslog: Jan  1 12:00:00
    re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'), # ISO: 2026-01-01T12:00:00
    re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'), # 2026-01-01 12:00:00
]


def scan_file(path, patterns, max_matches=500):
    results = {name: 0 for name in patterns}
    samples  = {name: '' for name in patterns}

    try:
        with open(path, 'r', errors='replace') as f:
            for line in f:
                for name, pat in patterns.items():
                    if re.search(pat, line, re.IGNORECASE):
                        results[name] += 1
                        if not samples[name]:
                            samples[name] = line.strip()[:100]
    except PermissionError:
        return None, None, f"Permission denied: {path}"
    except FileNotFoundError:
        return None, None, f"File not found: {path}"
    except Exception as e:
        return None, None, str(e)

    return results, samples, ''


def main():
    parser = make_base_parser('Scan log files with regex patterns and report match counts')
    parser.add_argument('--file', action='append', metavar='PATH',
                        help='Log file to scan (repeatable; overrides config)')
    parser.add_argument('--pattern', action='append', metavar='NAME=REGEX',
                        help='Additional pattern (name=regex)')
    args = parser.parse_args()
    apply_base_args(args)
    cfg = load_config(args.config)

    # Gather files
    files = args.file if args.file else cfg.watch_files
    if not files:
        files = ['/var/log/messages']

    # Build pattern dict
    patterns = dict(DEFAULT_PATTERNS)
    patterns.update(cfg.log_patterns)
    if args.pattern:
        for entry in args.pattern:
            if '=' in entry:
                k, _, v = entry.partition('=')
                patterns[k.strip()] = v.strip()

    all_rows = []
    errors   = []

    for filepath in files:
        filepath = os.path.expanduser(filepath)
        results, samples, err = scan_file(filepath, patterns)
        if err:
            errors.append(err)
            continue

        for name, count in results.items():
            if count == 0:
                continue
            status = 'WARN' if count >= 50 else ('INFO' if count >= 10 else 'OK')
            all_rows.append({
                'File':    os.path.basename(filepath),
                'Pattern': name,
                'Count':   str(count),
                'Sample':  (samples.get(name) or '')[:60],
                'Status':  status,
            })

    all_rows.sort(key=lambda r: (-int(r['Count']), r['File'], r['Pattern']))

    overall = ('warn' if any(r['Status']=='WARN' for r in all_rows) else
               'ok' if all_rows else 'ok')

    if args.json:
        out = ToolOutput(
            tool='log-summary',
            status=overall,
            summary=f"Scanned {len(files)} file(s), {sum(int(r['Count']) for r in all_rows)} total matches",
            records=all_rows,
            errors=errors,
        )
        emit_json(out)

    print_header('Log Summary')
    print(f"  Files scanned: {len(files)}   Patterns: {len(patterns)}\n")

    if all_rows:
        print_table(all_rows, columns=['File', 'Pattern', 'Count', 'Sample', 'Status'],
                    status_col='Status')
    else:
        print('  No pattern matches found.\n')

    if errors:
        print_section('Errors')
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    main()
