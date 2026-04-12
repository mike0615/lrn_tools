"""
lib/hosts.py — Remote host profiles and SSH execution for lrn_tools.

Host profiles are stored in ~/.lrn_tools/hosts.json (chmod 600).

Auth methods:
  key      — Uses the system `ssh` binary with a specified key file (or default
              ~/.ssh/id_rsa). Zero extra dependencies. Recommended.
  password — Requires `sshpass` (dnf install sshpass). Passwords are stored in
              plain text — use key auth whenever possible.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

HOSTS_FILE = Path.home() / '.lrn_tools' / 'hosts.json'


def _slugify(name: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return s or 'host'


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HostProfile:
    id: str
    name: str
    host: str
    port: int = 22
    user: str = 'root'
    auth_type: str = 'key'          # 'key' or 'password'
    key_path: str = ''              # e.g. ~/.ssh/id_rsa  (blank = ssh default)
    password: str = ''              # plain text — prefer key auth
    lrn_path: str = '~/dev/lrn_tools'
    notes: str = ''


# ---------------------------------------------------------------------------
# Host manager (CRUD)
# ---------------------------------------------------------------------------

class HostManager:

    def __init__(self, path: Path = HOSTS_FILE):
        self._path = path

    def _ensure(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text('[]')
            os.chmod(self._path, 0o600)

    def load(self) -> list:
        self._ensure()
        try:
            raw = json.loads(self._path.read_text())
            profiles = []
            for h in raw:
                try:
                    profiles.append(HostProfile(
                        id=h.get('id', ''),
                        name=h.get('name', ''),
                        host=h.get('host', ''),
                        port=int(h.get('port', 22)),
                        user=h.get('user', 'root'),
                        auth_type=h.get('auth_type', 'key'),
                        key_path=h.get('key_path', ''),
                        password=h.get('password', ''),
                        lrn_path=h.get('lrn_path', '~/dev/lrn_tools'),
                        notes=h.get('notes', ''),
                    ))
                except Exception:
                    continue
            return profiles
        except Exception:
            return []

    def save(self, profiles: list):
        self._ensure()
        self._path.write_text(json.dumps([asdict(p) for p in profiles], indent=2))
        os.chmod(self._path, 0o600)

    def get(self, host_id: str) -> Optional[HostProfile]:
        return next((h for h in self.load() if h.id == host_id), None)

    def add(self, profile: HostProfile) -> HostProfile:
        """Add profile, auto-generating a unique ID from the name."""
        profiles = self.load()
        existing_ids = {p.id for p in profiles}
        if not profile.id:
            profile.id = _slugify(profile.name)
        base = profile.id
        n = 1
        while profile.id in existing_ids:
            profile.id = f'{base}-{n}'
            n += 1
        profiles.append(profile)
        self.save(profiles)
        return profile

    def update(self, profile: HostProfile):
        profiles = self.load()
        for i, p in enumerate(profiles):
            if p.id == profile.id:
                profiles[i] = profile
                break
        self.save(profiles)

    def delete(self, host_id: str):
        self.save([p for p in self.load() if p.id != host_id])


# ---------------------------------------------------------------------------
# SSH command builders
# ---------------------------------------------------------------------------

def _ssh_cmd(profile: HostProfile, remote_cmd: str) -> list:
    """Build ssh command for key-based auth."""
    cmd = [
        'ssh',
        '-p', str(profile.port),
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=10',
        '-o', 'BatchMode=yes',
        '-o', 'ServerAliveInterval=30',
    ]
    if profile.key_path:
        cmd += ['-i', os.path.expanduser(profile.key_path)]
    cmd.append(f'{profile.user}@{profile.host}')
    cmd.append(remote_cmd)
    return cmd


def _sshpass_cmd(profile: HostProfile, remote_cmd: str) -> list:
    """Build sshpass + ssh command for password auth."""
    ssh = [
        'ssh',
        '-p', str(profile.port),
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=10',
        '-o', 'BatchMode=no',
        '-o', 'PasswordAuthentication=yes',
        '-o', 'ServerAliveInterval=30',
        f'{profile.user}@{profile.host}',
        remote_cmd,
    ]
    return ['sshpass', '-p', profile.password] + ssh


def _build_cmd(profile: HostProfile, remote_cmd: str) -> tuple:
    """
    Return (cmd_list, error_str).
    error_str is non-empty if we cannot build the command (missing sshpass).
    """
    if profile.auth_type == 'password':
        if not shutil.which('sshpass'):
            return [], (
                'sshpass is not installed. '
                'Install it with: dnf install sshpass\n'
                'Or switch to key-based authentication.'
            )
        return _sshpass_cmd(profile, remote_cmd), ''
    return _ssh_cmd(profile, remote_cmd), ''


# ---------------------------------------------------------------------------
# Remote tool path helper
# ---------------------------------------------------------------------------

def tool_rel_path(tool: dict) -> str:
    """
    Return the path of a tool relative to the lrn_tools project root.
    e.g. 'tools/system/sysinfo.py'
    """
    try:
        from lib.registry import _ROOT
        return os.path.relpath(tool['path'], _ROOT)
    except Exception:
        return tool['path']


def _remote_python(profile: HostProfile, rel_path: str, extra_args: list) -> str:
    """Build the remote python command string."""
    lrn = profile.lrn_path.rstrip('/')
    # Use python3 -u for unbuffered output (critical for streaming)
    safe_args = ' '.join(a for a in extra_args)
    return f'python3 -u {lrn}/{rel_path} {safe_args}'.strip()


# ---------------------------------------------------------------------------
# Remote execution
# ---------------------------------------------------------------------------

def run_remote(profile: HostProfile, rel_path: str, extra_args: list) -> tuple:
    """
    Run a tool on a remote host via SSH.
    Returns (stdout: str, stderr: str, returncode: int).
    """
    remote_cmd = _remote_python(profile, rel_path, extra_args)
    cmd, err = _build_cmd(profile, remote_cmd)
    if err:
        return '', err, 1

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            errors='replace',
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return '', 'SSH command timed out after 120 seconds.', 1
    except FileNotFoundError as e:
        return '', f'SSH binary not found: {e}. Is OpenSSH client installed?', 1
    except Exception as e:
        return '', f'SSH error: {e}', 1


def stream_remote(profile: HostProfile, rel_path: str, extra_args: list):
    """
    Stream output from a tool running on a remote host.
    Yields text lines.  Final yield is the string '__EXIT__<code>'.
    """
    remote_cmd = _remote_python(profile, rel_path, extra_args)
    cmd, err = _build_cmd(profile, remote_cmd)
    if err:
        yield f'ERROR: {err}\n'
        yield '__EXIT__1'
        return

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors='replace',
        )
        for line in iter(proc.stdout.readline, ''):
            yield line
        proc.wait()
        yield f'__EXIT__{proc.returncode}'
    except FileNotFoundError as e:
        yield f'ERROR: SSH binary not found: {e}\n'
        yield '__EXIT__1'
    except Exception as e:
        yield f'SSH ERROR: {e}\n'
        yield '__EXIT__1'


# ---------------------------------------------------------------------------
# Deploy lrn_tools to a remote host
# ---------------------------------------------------------------------------

def deploy_lrn_tools(profile: HostProfile, local_path: str):
    """
    Deploy lrn_tools to a remote host using rsync over SSH.
    Yields progress lines; final yield is '__EXIT__<code>'.

    local_path : absolute path to lrn_tools on this server (e.g. /opt/lrn_tools)
    The remote destination is profile.lrn_path.
    """
    if not shutil.which('rsync'):
        yield 'ERROR: rsync is not installed on this server.\n'
        yield 'Install with: dnf install rsync\n'
        yield '__EXIT__1'
        return

    remote_dest = f'{profile.user}@{profile.host}:{profile.lrn_path}'

    # Build ssh options string for rsync -e
    ssh_opts = (
        f'ssh -p {profile.port}'
        f' -o StrictHostKeyChecking=no'
        f' -o ConnectTimeout=10'
    )
    if profile.auth_type == 'key' and profile.key_path:
        ssh_opts += f' -i {os.path.expanduser(profile.key_path)}'
    elif profile.auth_type == 'key':
        ssh_opts += ' -o BatchMode=yes'

    rsync_cmd = [
        'rsync', '-avz', '--delete', '--progress',
        '--exclude=.git',
        '--exclude=__pycache__',
        '--exclude=*.pyc',
        '--exclude=*.log',
        '--exclude=hosts.json',
        '-e', ssh_opts,
        f'{local_path.rstrip("/")}/',
        f'{remote_dest}/',
    ]

    # Wrap with sshpass for password auth
    if profile.auth_type == 'password':
        if not shutil.which('sshpass'):
            yield 'ERROR: sshpass not installed (dnf install sshpass)\n'
            yield '__EXIT__1'
            return
        rsync_cmd = ['sshpass', '-p', profile.password] + rsync_cmd

    # Ensure remote directory exists first
    mkdir_cmd, err = _build_cmd(profile, f'mkdir -p {profile.lrn_path}')
    if err:
        yield f'ERROR: {err}\n'
        yield '__EXIT__1'
        return

    yield f'=== Deploying lrn_tools to {profile.name} ===\n'
    yield f'  Source : {local_path}\n'
    yield f'  Target : {profile.user}@{profile.host}:{profile.lrn_path}\n'
    yield f'  Auth   : {profile.auth_type}\n'
    yield '---\n'
    yield 'Creating remote directory...\n'

    subprocess.run(mkdir_cmd, capture_output=True, timeout=15)

    yield 'Starting rsync transfer...\n\n'

    try:
        proc = subprocess.Popen(
            rsync_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors='replace',
        )
        for line in iter(proc.stdout.readline, ''):
            yield line
        proc.wait()
        if proc.returncode == 0:
            yield '\n=== Transfer complete ===\n'
            yield f'\nNext step — run on {profile.host}:\n'
            yield f'  bash {profile.lrn_path}/install.sh\n'
            yield '\nOr to start the web dashboard immediately:\n'
            yield f'  python3 {profile.lrn_path}/web/app.py --host 0.0.0.0 --port 5000\n'
        else:
            yield f'\nrsync exited with code {proc.returncode}\n'
        yield f'__EXIT__{proc.returncode}'
    except Exception as e:
        yield f'ERROR: {e}\n'
        yield '__EXIT__1'


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

def test_connection(profile: HostProfile) -> tuple:
    """
    Test SSH connectivity and verify lrn_tools is present.
    Returns (success: bool, message: str).
    """
    # Step 1: basic SSH connectivity
    cmd, err = _build_cmd(profile, 'echo __LRNPING__')
    if err:
        return False, err

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or '__LRNPING__' not in result.stdout:
            detail = (result.stderr or result.stdout or 'No response').strip()
            return False, f'SSH failed: {detail[:300]}'
    except subprocess.TimeoutExpired:
        return False, f'Connection timed out — is {profile.host}:{profile.port} reachable?'
    except FileNotFoundError as e:
        return False, f'SSH binary not found: {e}'
    except Exception as e:
        return False, str(e)

    # Step 2: verify lrn_tools at configured path
    lrn = profile.lrn_path.rstrip('/')
    check_cmd = f'test -f {lrn}/lib/common.py && echo __LRNOK__ || echo __LRNMISSING__'
    cmd2, _ = _build_cmd(profile, check_cmd)
    try:
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        if '__LRNOK__' in r2.stdout:
            return True, f'Connected to {profile.user}@{profile.host}:{profile.port} — lrn_tools found at {profile.lrn_path}'
        elif '__LRNMISSING__' in r2.stdout:
            return True, (
                f'Connected to {profile.user}@{profile.host}:{profile.port} — '
                f'WARNING: lrn_tools not found at {profile.lrn_path}. '
                'Clone the repo there before running tools remotely.'
            )
        else:
            return True, f'Connected to {profile.user}@{profile.host}:{profile.port} (lrn_tools path unverified)'
    except Exception:
        return True, f'Connected to {profile.user}@{profile.host}:{profile.port} (could not verify lrn_tools path)'
