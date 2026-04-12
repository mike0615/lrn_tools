#!/usr/bin/env python3
"""
web/app.py — Flask web dashboard for lrn_tools.

Usage:
    python3 web/app.py                    # start on 127.0.0.1:5000
    python3 web/app.py --host 0.0.0.0     # listen on all interfaces
    python3 web/app.py --port 8080

Requires: python3-flask  (dnf install python3-flask)
"""

import json
import os
import subprocess
import sys
import time
import argparse
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from flask import (Flask, render_template, request, jsonify,
                       Response, stream_with_context, redirect, url_for, flash)
except ImportError:
    print("Flask not found. Install with: dnf install python3-flask")
    sys.exit(1)

from lib.registry import TOOLS, get_categories, get_tools_by_category, get_tool_by_id
from lib.config import load_config
from lib.hosts import HostManager, HostProfile, test_connection, tool_rel_path, run_remote, stream_remote

host_manager = HostManager()

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_path=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    cfg = load_config(config_path)

    app.secret_key = cfg.web_secret_key
    app.config['TOOL_TIMEOUT'] = cfg.tool_timeout
    app.config['SITE_NAME']    = cfg.site_name

    # Inject registry + hosts into every template
    @app.context_processor
    def inject_globals():
        profiles = host_manager.load()
        # Expose sanitized host list (no password field in templates)
        safe_hosts = [
            {'id': p.id, 'name': p.name, 'host': p.host,
             'user': p.user, 'port': p.port, 'auth_type': p.auth_type,
             'lrn_path': p.lrn_path, 'notes': p.notes}
            for p in profiles
        ]
        return {
            'categories':   get_categories(),
            'tools_by_cat': get_tools_by_category(),
            'site_name':    cfg.site_name,
            'hosts':        safe_hosts,
        }

    # ── Dashboard ────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/tool/<tool_id>')
    def tool_page(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return "Tool not found", 404
        return render_template('tool_run.html', tool=tool)

    # ── Tool execution — local ───────────────────────────────────────────────

    def _local_run(tool, arg_list):
        """Run a tool locally. Returns JSON-serialisable dict."""
        args = [sys.executable, tool['path']]
        if tool.get('json_capable'):
            args.append('--json')
        args += arg_list

        start = time.monotonic()
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True,
                timeout=120, errors='replace',
            )
            elapsed = int((time.monotonic() - start) * 1000)
            json_data = None
            if tool.get('json_capable') and proc.stdout:
                try:
                    json_data = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    pass
            return {
                'exit_code':   proc.returncode,
                'stdout':      proc.stdout,
                'stderr':      proc.stderr,
                'duration_ms': elapsed,
                'json_data':   json_data,
                'target':      'local',
            }
        except subprocess.TimeoutExpired:
            return {'exit_code': -1, 'error': 'Tool timed out after 120s', 'target': 'local'}
        except Exception as e:
            return {'exit_code': -1, 'error': str(e), 'target': 'local'}

    def _remote_run(tool, profile, arg_list):
        """Run a tool on a remote host via SSH. Returns JSON-serialisable dict."""
        rel = tool_rel_path(tool)
        if tool.get('json_capable'):
            arg_list = ['--json'] + arg_list

        start = time.monotonic()
        stdout, stderr, rc = run_remote(profile, rel, arg_list)
        elapsed = int((time.monotonic() - start) * 1000)

        json_data = None
        if tool.get('json_capable') and stdout:
            try:
                json_data = json.loads(stdout)
            except json.JSONDecodeError:
                pass

        return {
            'exit_code':   rc,
            'stdout':      stdout,
            'stderr':      stderr,
            'duration_ms': elapsed,
            'json_data':   json_data,
            'target':      f'{profile.name} ({profile.user}@{profile.host})',
        }

    # ── /run  (POST — blocking) ──────────────────────────────────────────────

    @app.route('/run/<tool_id>', methods=['POST'])
    def run_tool(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return jsonify({'error': 'Tool not found'}), 404

        extra_args = request.form.get('args', '').strip()
        host_id    = request.form.get('host_id', 'local').strip()
        arg_list   = extra_args.split() if extra_args else []

        if host_id and host_id != 'local':
            profile = host_manager.get(host_id)
            if not profile:
                return jsonify({'error': f'Host profile not found: {host_id}', 'exit_code': 1}), 404
            return jsonify(_remote_run(tool, profile, arg_list))

        return jsonify(_local_run(tool, arg_list))

    # ── /stream  (GET — SSE) ─────────────────────────────────────────────────

    @app.route('/stream/<tool_id>')
    def stream_tool(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return "Tool not found", 404

        extra_args = request.args.get('args', '').strip()
        host_id    = request.args.get('host_id', 'local').strip()
        arg_list   = extra_args.split() if extra_args else []

        def _sse(line):
            return f"data: {json.dumps(line)}\n\n"

        if host_id and host_id != 'local':
            profile = host_manager.get(host_id)
            if not profile:
                def gen_err():
                    yield _sse(f'ERROR: Host not found: {host_id}\n')
                    yield _sse('__EXIT__1')
                return Response(stream_with_context(gen_err()),
                                mimetype='text/event-stream',
                                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

            rel = tool_rel_path(tool)

            def gen_remote():
                for chunk in stream_remote(profile, rel, arg_list):
                    yield _sse(chunk)

            return Response(stream_with_context(gen_remote()),
                            mimetype='text/event-stream',
                            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

        # Local stream
        args = [sys.executable, tool['path']] + arg_list

        def gen_local():
            try:
                proc = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors='replace',
                )
                for line in proc.stdout:
                    yield _sse(line)
                proc.wait()
                yield _sse(f'__EXIT__{proc.returncode}')
            except Exception as e:
                yield _sse(f'ERROR: {e}\n')
                yield _sse('__EXIT__1')

        return Response(stream_with_context(gen_local()),
                        mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # ── Host management ──────────────────────────────────────────────────────

    @app.route('/hosts')
    def hosts_page():
        profiles = host_manager.load()
        return render_template('hosts.html', profiles=profiles)

    @app.route('/hosts/new', methods=['GET', 'POST'])
    def host_new():
        if request.method == 'POST':
            profile = HostProfile(
                id='',
                name=request.form.get('name', '').strip(),
                host=request.form.get('host', '').strip(),
                port=int(request.form.get('port', 22) or 22),
                user=request.form.get('user', 'root').strip(),
                auth_type=request.form.get('auth_type', 'key'),
                key_path=request.form.get('key_path', '').strip(),
                password=request.form.get('password', '').strip(),
                lrn_path=request.form.get('lrn_path', '~/dev/lrn_tools').strip(),
                notes=request.form.get('notes', '').strip(),
            )
            if not profile.name or not profile.host:
                return render_template('host_form.html', profile=profile,
                                       action='new', error='Name and Host are required.')
            host_manager.add(profile)
            return redirect(url_for('hosts_page'))
        return render_template('host_form.html', profile=None, action='new', error=None)

    @app.route('/hosts/<host_id>/edit', methods=['GET', 'POST'])
    def host_edit(host_id):
        profile = host_manager.get(host_id)
        if not profile:
            return "Host not found", 404
        if request.method == 'POST':
            profile.name      = request.form.get('name', profile.name).strip()
            profile.host      = request.form.get('host', profile.host).strip()
            profile.port      = int(request.form.get('port', profile.port) or 22)
            profile.user      = request.form.get('user', profile.user).strip()
            profile.auth_type = request.form.get('auth_type', profile.auth_type)
            profile.key_path  = request.form.get('key_path', profile.key_path).strip()
            # Only update password if a new one was supplied
            new_pw = request.form.get('password', '').strip()
            if new_pw:
                profile.password = new_pw
            profile.lrn_path  = request.form.get('lrn_path', profile.lrn_path).strip()
            profile.notes     = request.form.get('notes', profile.notes).strip()
            if not profile.name or not profile.host:
                return render_template('host_form.html', profile=profile,
                                       action='edit', error='Name and Host are required.')
            host_manager.update(profile)
            return redirect(url_for('hosts_page'))
        return render_template('host_form.html', profile=profile, action='edit', error=None)

    @app.route('/hosts/<host_id>/delete', methods=['POST'])
    def host_delete(host_id):
        host_manager.delete(host_id)
        return redirect(url_for('hosts_page'))

    @app.route('/hosts/<host_id>/test', methods=['POST'])
    def host_test(host_id):
        profile = host_manager.get(host_id)
        if not profile:
            return jsonify({'success': False, 'message': f'Host not found: {host_id}'}), 404
        success, message = test_connection(profile)
        return jsonify({'success': success, 'message': message})

    # ── JSON API ─────────────────────────────────────────────────────────────

    @app.route('/api/tools')
    def api_tools():
        return jsonify(TOOLS)

    @app.route('/api/categories')
    def api_categories():
        return jsonify(get_categories())

    @app.route('/api/hosts')
    def api_hosts():
        profiles = host_manager.load()
        return jsonify([
            {'id': p.id, 'name': p.name, 'host': p.host,
             'user': p.user, 'port': p.port, 'auth_type': p.auth_type,
             'lrn_path': p.lrn_path, 'notes': p.notes}
            for p in profiles
        ])

    return app


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='LRN Tools Web Dashboard')
    parser.add_argument('--host',   default=None, help='Bind host (default from config)')
    parser.add_argument('--port',   type=int, default=None, help='Bind port (default from config)')
    parser.add_argument('--config', default=os.path.expanduser('~/.lrn_tools/config.ini'),
                        help='Config file path')
    parser.add_argument('--debug',  action='store_true', help='Enable Flask debug mode')
    args = parser.parse_args()

    cfg = load_config(args.config)
    app = create_app(args.config)

    host  = args.host  or cfg.web_host
    port  = args.port  or cfg.web_port
    debug = args.debug or cfg.web_debug

    print(f"LRN Tools Web Dashboard starting on http://{host}:{port}")
    print(f"Site: {cfg.site_name}   Config: {args.config}")
    print("Press Ctrl+C to stop.\n")

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()
