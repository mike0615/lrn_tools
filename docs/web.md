# Web Dashboard (`lrn-web`)

The web dashboard is a Flask-based browser interface for running tools, viewing structured reports, and streaming live tool output. It is fully self-contained — no CDN, no external fonts, no JavaScript frameworks. Safe for air-gapped networks.

---

## Starting the Dashboard

```bash
lrn-web                          # binds to 127.0.0.1:5000 (config default)
lrn-web --host 0.0.0.0           # listen on all interfaces
lrn-web --port 8080              # custom port
lrn-web --debug                  # Flask debug mode (dev only)
```

Or directly:

```bash
python3 ~/dev/lrn_tools/web/app.py
```

Open a browser and navigate to `http://127.0.0.1:5000` (or whichever host/port you configured).

### Requirement

Flask must be installed:

```bash
dnf install python3-flask
```

---

## Running as a System Service

If `install.sh` was run as root, a systemd unit is already present:

```bash
sudo systemctl enable --now lrn-web
sudo systemctl status lrn-web
journalctl -u lrn-web -f          # follow logs
```

To expose on LAN, set `host = 0.0.0.0` in `[web]` config, then open the firewall:

```bash
sudo firewall-cmd --add-port=5000/tcp --permanent && sudo firewall-cmd --reload
```

---

## Interface Overview

### Dashboard (`/`)

The home page shows all tool categories as cards. Each card lists the tools in that category as clickable chips. Click any tool to go to its run page.

```
┌─────────────────────────────────────────────────────────────┐
│ ▲ LRN Tools   LRN Lab              Dashboard               │
├──────────┬──────────────────────────────────────────────────┤
│ ⌂ Dashboard│  🌐 DNS                     3 tools            │
│ ─────────│  [Generate Reverse Zones] [DNS Query Test]      │
│ DNS      │  [Zone Consistency Check]                       │
│  Gen Rev │                                                  │
│  Query   │  🔑 FreeIPA                   3 tools           │
│  Consist │  [IPA Health Check] [User Report] [Host Inv]    │
│ ─────────│                                                  │
│ FreeIPA  │  📃 Certificates              2 tools           │
│  Health  │  [Certificate Inventory] [Expiry Check]         │
│  Users   │                                                  │
│  Hosts   │  🖥 System                    3 tools            │
│ ─────────│  [System Info] [Service Status] [Triage]        │
└──────────┴──────────────────────────────────────────────────┘
```

### Tool Run Page (`/tool/<id>`)

Each tool has a dedicated page with:

1. **Description** — what the tool does
2. **Arguments input** — free-text field for extra CLI flags
3. **Run / Stream buttons** — two ways to execute the tool
4. **JSON view toggle** — switch between raw terminal output and structured report
5. **Output panel** — monospace terminal display or formatted report table

---

## Running a Tool

### Standard Run (POST)

Click **Run** or submit the form. The web server:

1. Executes the tool with `--json` (if the tool supports it)
2. Waits for it to complete (up to `tool_timeout` seconds)
3. Returns all output at once
4. Renders: raw terminal text in the output panel, structured table if JSON is available

Best for: tools that complete in a few seconds.

### Streamed Run (SSE)

Click **Stream (live)**. The web server:

1. Starts the tool as a subprocess (without `--json`)
2. Streams stdout line-by-line to the browser via Server-Sent Events
3. The output panel updates in real time
4. A final `__EXIT__<code>` message signals completion

Best for: long-running tools like connectivity sweeps or log scans.

---

## JSON Report View

When a tool supports `--json` and the run completes successfully, a **JSON view** toggle appears. Enabling it renders the `records` array as a formatted HTML table with:

- Column headers from the record field names
- Status badges (colored OK / WARN / CRIT / ERROR) for any field named `Status` or `status`
- Row background tinting based on status
- A summary line and timestamp from the tool output

Toggle back to **raw view** at any time to see the original terminal output.

---

## Arguments Field

The arguments text field accepts any flags the tool supports. The string is split on spaces and appended to the tool invocation. Examples:

| Tool page | Arguments input | Effective command |
|-----------|----------------|-------------------|
| DNS Query Test | `--name ipa01.lrn.local --type A` | `dns-query-test.py --json --name ipa01.lrn.local --type A` |
| Journal Errors | `--hours 48 --unit httpd` | `journal-errors.py --json --hours 48 --unit httpd` |
| Cert Expiry | `--days 60` | `cert-expiry-check.py --json --days 60` |
| Service Status | `--all-failed` | `service-status.py --json --all-failed` |

For tools that take positional arguments (like `gen-reverse-zones.py`), include the positional value first:

```
/var/named/db.lrn.local --dry-run
```

---

## API Endpoints

The web app exposes a small JSON API for scripting or integration:

### `GET /api/tools`

Returns the full tool registry as JSON.

```bash
curl http://127.0.0.1:5000/api/tools | python3 -m json.tool
```

### `GET /api/categories`

Returns the list of tool category names.

```bash
curl http://127.0.0.1:5000/api/categories
```

### `POST /run/<tool_id>`

Runs a tool and returns its output as JSON. Form parameter: `args` (optional extra flags).

```bash
curl -s -X POST http://127.0.0.1:5000/run/sys-info \
     -d "args=" | python3 -m json.tool
```

Response schema:

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "duration_ms": 312,
  "json_data": { ... }
}
```

### `GET /stream/<tool_id>?args=<flags>`

SSE stream endpoint. Returns `text/event-stream`. Each event is a JSON-encoded output line. The final event is `__EXIT__<code>`.

```bash
curl -N http://127.0.0.1:5000/stream/sys-info
```

---

## Security Notes

- By default, the dashboard binds to `127.0.0.1` only — not accessible from the network.
- If exposing on LAN (`host = 0.0.0.0`), protect it with firewall rules restricting access to trusted hosts.
- The web app runs tools as the user that started `lrn-web`. Tools that need root (e.g., some `virsh` operations) must be run by root.
- Change `secret_key` in config before any multi-user or network-accessible deployment.
- Flask debug mode (`debug = true`) exposes an interactive debugger. **Never enable in production.**

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `lrn-web` not found | Check `~/bin` is in PATH (non-root) or Flask symlink was not created |
| `ModuleNotFoundError: flask` | `dnf install python3-flask` |
| Tool times out | Increase `[general] tool_timeout` in config |
| Blank output panel | Check browser console for JavaScript errors; ensure Flask is not in debug/error state |
| SSE stream stops immediately | Some reverse proxies (nginx) buffer SSE — add `proxy_buffering off` |
