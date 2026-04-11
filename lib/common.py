#!/usr/bin/env python3
"""
lib/common.py — Shared utilities for all lrn_tools scripts.

Provides: colored output, subprocess execution, table formatting,
JSON output schema, and a base argument parser.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Color control
# ---------------------------------------------------------------------------

_USE_COLOR: bool = sys.stdout.isatty() and os.environ.get('NO_COLOR', '') == ''


def set_color_mode(enabled: bool) -> None:
    global _USE_COLOR
    _USE_COLOR = enabled


class C:
    """ANSI color codes."""
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    RED    = '\033[31m'
    GREEN  = '\033[32m'
    YELLOW = '\033[33m'
    CYAN   = '\033[36m'
    WHITE  = '\033[37m'
    BRED   = '\033[91m'
    BGREEN = '\033[92m'
    BYELLOW= '\033[93m'
    BCYAN  = '\033[96m'


def _c(code: str, text: str) -> str:
    return f"{code}{text}{C.RESET}" if _USE_COLOR else text


def strip_ansi(text: str) -> str:
    return re.sub(r'\033\[[0-9;]*m', '', text)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_header(title: str) -> None:
    bar = '=' * (len(title) + 4)
    print(f"\n{_c(C.BOLD+C.BCYAN, bar)}")
    print(f"{_c(C.BOLD+C.BCYAN, f'  {title}')}")
    print(f"{_c(C.BOLD+C.BCYAN, bar)}\n")


def print_section(title: str) -> None:
    print(f"\n{_c(C.BOLD+C.CYAN, f'--- {title} ---')}")


def print_ok(msg: str) -> None:
    print(f"  {_c(C.BGREEN, '[OK]')}   {msg}")


def print_warn(msg: str) -> None:
    print(f"  {_c(C.BYELLOW, '[WARN]')} {msg}")


def print_crit(msg: str) -> None:
    print(f"  {_c(C.BRED, '[CRIT]')} {msg}")


def print_error(msg: str) -> None:
    print(f"  {_c(C.RED, '[ERR]')}  {msg}", file=sys.stderr)


def print_info(msg: str) -> None:
    print(f"  {_c(C.CYAN, '[INFO]')} {msg}")


def status_badge(status: str) -> str:
    """Return a colorized status string. status: ok|warn|crit|error|unknown."""
    s = status.lower()
    if s in ('ok', 'active', 'running', 'open', 'pass', 'healthy'):
        return _c(C.BGREEN, status.upper())
    if s in ('warn', 'warning', 'degraded', 'stale'):
        return _c(C.BYELLOW, status.upper())
    if s in ('crit', 'critical', 'error', 'failed', 'closed', 'inactive', 'dead'):
        return _c(C.BRED, status.upper())
    return _c(C.WHITE, status.upper())


# ---------------------------------------------------------------------------
# Subprocess execution
# ---------------------------------------------------------------------------

@dataclass
class CmdResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


def run_cmd(
    args: list,
    timeout: int = 30,
    input_text: Optional[str] = None,
    env: Optional[dict] = None,
    check: bool = False,
    shell: bool = False,
) -> CmdResult:
    """
    Run a subprocess. Never raises on non-zero exit unless check=True.
    Returns CmdResult with decoded stdout/stderr.
    """
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=input_text.encode() if input_text else None,
            timeout=timeout,
            env=env,
            shell=shell,
        )
        result = CmdResult(
            stdout=proc.stdout.decode('utf-8', errors='replace').rstrip(),
            stderr=proc.stderr.decode('utf-8', errors='replace').rstrip(),
            returncode=proc.returncode,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"Command {args[0]!r} failed (exit {proc.returncode}):\n{result.stderr}"
            )
        return result
    except subprocess.TimeoutExpired:
        return CmdResult(stdout='', stderr=f'Command timed out after {timeout}s', returncode=-1, timed_out=True)
    except FileNotFoundError:
        return CmdResult(stdout='', stderr=f"Command not found: {args[0]}", returncode=127)


def require_command(cmd: str, install_hint: str = '') -> None:
    """Exit with a helpful message if cmd is not on PATH."""
    if shutil.which(cmd) is None:
        msg = f"Required command '{cmd}' not found."
        if install_hint:
            msg += f" Install with: {install_hint}"
        print_error(msg)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

def format_table(
    rows: list,
    columns: Optional[list] = None,
    status_col: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Return an aligned ASCII table as a string."""
    if not rows:
        return '  (no data)\n'

    if columns is None:
        columns = list(rows[0].keys())

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ''))
            widths[col] = max(widths[col], len(strip_ansi(val)))

    def fmt_row(row_dict, header=False):
        parts = []
        for col in columns:
            raw = str(row_dict.get(col, '')) if not header else col
            if header:
                cell = _c(C.BOLD, raw.ljust(widths[col]))
            elif col == status_col:
                cell = status_badge(raw).ljust(widths[col] + (len(status_badge(raw)) - len(strip_ansi(status_badge(raw)))))
            else:
                cell = raw.ljust(widths[col])
            parts.append(cell)
        return '  ' + '  '.join(parts)

    sep = '  ' + '  '.join('-' * widths[col] for col in columns)

    lines = []
    if title:
        lines.append(f"\n{_c(C.BOLD+C.CYAN, title)}")
    lines.append(fmt_row({}, header=True))
    lines.append(sep)
    for row in rows:
        lines.append(fmt_row(row))
    lines.append('')
    return '\n'.join(lines)


def print_table(
    rows: list,
    columns: Optional[list] = None,
    status_col: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    print(format_table(rows, columns=columns, status_col=status_col, title=title))


# ---------------------------------------------------------------------------
# Standard JSON output schema
# ---------------------------------------------------------------------------

@dataclass
class ToolOutput:
    tool: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + 'Z')
    status: str = 'ok'          # ok | warn | crit | error | mixed
    summary: str = ''
    records: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def emit_json(output: ToolOutput) -> None:
    """Serialize ToolOutput to stdout as JSON and exit."""
    print(json.dumps(asdict(output), indent=2))
    sys.exit(0 if output.status in ('ok',) else (2 if output.status in ('warn', 'mixed') else 1))


def emit_json_error(msg: str, tool: str) -> None:
    out = ToolOutput(tool=tool, status='error', summary=msg, errors=[msg])
    print(json.dumps(asdict(out), indent=2))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Base argument parser
# ---------------------------------------------------------------------------

def make_base_parser(description: str, epilog: Optional[str] = None) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--json',     action='store_true', help='Emit machine-readable JSON output')
    p.add_argument('--no-color', action='store_true', help='Disable ANSI color codes')
    p.add_argument('--quiet',    action='store_true', help='Suppress informational output')
    p.add_argument('--config',   metavar='PATH',
                   default=os.path.expanduser('~/.lrn_tools/config.ini'),
                   help='Config file path (default: ~/.lrn_tools/config.ini)')
    return p


def apply_base_args(args: argparse.Namespace) -> None:
    """Apply universal flags from parsed args. Call once at tool startup."""
    if args.no_color:
        set_color_mode(False)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def days_until(dt: datetime.datetime) -> int:
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return (dt - now).days


def format_bytes(n: int) -> str:
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def is_root() -> bool:
    return os.geteuid() == 0


def parse_size_to_bytes(s: str) -> int:
    """Parse '4.00 GiB' or '512 MiB' style strings to integer bytes."""
    m = re.match(r'([\d.]+)\s*([KMGTP]?i?B?)', s.strip(), re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper().rstrip('B').rstrip('I')
    mult = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4, 'P': 1024**5}
    return int(val * mult.get(unit, 1))
