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
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from flask import (Flask, render_template, request, jsonify,
                       Response, stream_with_context, redirect, url_for)
except ImportError:
    print("Flask not found. Install with: dnf install python3-flask")
    sys.exit(1)

from lib.registry import TOOLS, get_categories, get_tools_by_category, get_tool_by_id
from lib.config import load_config

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_path=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    cfg = load_config(config_path)

    app.secret_key = cfg.web_secret_key
    app.config['TOOL_TIMEOUT'] = cfg.tool_timeout
    app.config['SITE_NAME']    = cfg.site_name

    # Make registry available to all templates
    @app.context_processor
    def inject_registry():
        return {
            'categories':   get_categories(),
            'tools_by_cat': get_tools_by_category(),
            'site_name':    cfg.site_name,
        }

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/tool/<tool_id>')
    def tool_page(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return "Tool not found", 404
        return render_template('tool_run.html', tool=tool)

    @app.route('/run/<tool_id>', methods=['POST'])
    def run_tool(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return jsonify({'error': 'Tool not found'}), 404

        extra_args = request.form.get('args', '').strip()
        args       = [sys.executable, tool['path']]
        if tool.get('json_capable'):
            args.append('--json')
        if extra_args:
            args += extra_args.split()

        start = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=app.config['TOOL_TIMEOUT'],
            )
            elapsed = int((time.monotonic() - start) * 1000)
            stdout  = proc.stdout
            stderr  = proc.stderr
            rc      = proc.returncode

            json_data = None
            if tool.get('json_capable') and stdout:
                try:
                    json_data = json.loads(stdout)
                except json.JSONDecodeError:
                    pass

            return jsonify({
                'exit_code':   rc,
                'stdout':      stdout,
                'stderr':      stderr,
                'duration_ms': elapsed,
                'json_data':   json_data,
            })
        except subprocess.TimeoutExpired:
            return jsonify({'error': f'Tool timed out after {app.config["TOOL_TIMEOUT"]}s',
                            'exit_code': -1}), 408
        except Exception as e:
            return jsonify({'error': str(e), 'exit_code': -1}), 500

    @app.route('/stream/<tool_id>')
    def stream_tool(tool_id):
        tool = get_tool_by_id(tool_id)
        if not tool:
            return "Tool not found", 404

        extra_args = request.args.get('args', '').strip()
        args = [sys.executable, tool['path']]
        if extra_args:
            args += extra_args.split()

        def generate():
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors='replace',
                )
                for line in proc.stdout:
                    yield f"data: {json.dumps(line)}\n\n"
                proc.wait()
                yield f"data: {json.dumps(f'__EXIT__{proc.returncode}')}\n\n"
            except Exception as e:
                yield f"data: {json.dumps(f'ERROR: {e}')}\n\n"
                yield f"data: {json.dumps('__EXIT__1')}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )

    @app.route('/api/tools')
    def api_tools():
        return jsonify(TOOLS)

    @app.route('/api/categories')
    def api_categories():
        return jsonify(get_categories())

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
