# Docker Tools

Tools for monitoring Docker container health and Docker Compose project status.

| Tool | Script | Requires |
|------|--------|----------|
| Container Status | `tools/docker/container-status.py` | `docker` |
| Compose Health | `tools/docker/compose-health.py` | `docker` with Compose plugin (v2) or `docker-compose` (v1) |

### Prerequisites

```bash
# Docker CE
dnf install docker-ce docker-ce-cli containerd.io

# Or Podman with Docker compatibility shim
dnf install podman podman-docker
```

The user running these tools must be able to run `docker` commands. Either run as root or add the user to the `docker` group:

```bash
sudo usermod -aG docker $USER
# Log out and back in
```

---

## container-status.py

Lists all Docker containers (or only running ones) with their image, state, port mappings, and creation time. Also displays the local image inventory.

### Syntax

```
python3 tools/docker/container-status.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--running` | off | Show only running containers (exclude stopped, exited, etc.) |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**List all containers and images:**

```bash
python3 tools/docker/container-status.py
```

**List only running containers:**

```bash
python3 tools/docker/container-status.py --running
```

**JSON output:**

```bash
python3 tools/docker/container-status.py --json
```

**Count containers by state:**

```bash
python3 tools/docker/container-status.py --json | \
    python3 -c "
import json, sys
from collections import Counter
d = json.load(sys.stdin)
containers = [r for r in d['records'] if r.get('section') == 'containers']
counts = Counter(r['State'] for r in containers)
for state, count in sorted(counts.items()):
    print(f'  {state}: {count}')
"
```

**Find containers with port 443 exposed:**

```bash
python3 tools/docker/container-status.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if '443' in str(r.get('Ports', '')):
        print(r['Name'], '->', r['Ports'])
"
```

### Sample Output

```
========================================
  Docker Container Status
========================================

--- Containers (5 total) ---
  Name          Image                    State    Ports         Created               Status
  ────────────  ───────────────────────  ───────  ────────────  ────────────────────  ──────
  nginx-proxy   nginx:1.25               running  0.0.0.0:443   2026-04-01 10:00:00   OK
  gitlab        gitlab/gitlab-ce:latest  running  0.0.0.0:8080  2026-03-15 09:00:00   OK
  registry      registry:2               running  0.0.0.0:5000  2026-03-10 08:00:00   OK
  old-test      alpine:3.18              exited   -             2026-01-05 12:00:00   INFO
  broken-svc    myapp:1.0               exited   8443          2026-04-10 14:00:00   INFO

--- Images (8 total) ---
  Image                         Size        Created
  ────────────────────────────  ──────────  ──────────────────
  nginx:1.25                    187 MB      2026-03-01 00:00:00
  gitlab/gitlab-ce:latest       2.87 GB     2026-04-01 00:00:00
  registry:2                    26.2 MB     2026-02-15 00:00:00
  alpine:3.18                   7.34 MB     2025-12-01 00:00:00
```

### JSON Record Schema

The JSON output contains two record types differentiated by the `section` field:

**Container record (`section: "containers"`):**

```json
{
  "section": "containers",
  "Name": "nginx-proxy",
  "Image": "nginx:1.25",
  "State": "running",
  "Ports": "0.0.0.0:443->443/tcp",
  "Created": "2026-04-01 10:00:00",
  "Status": "OK"
}
```

**Image record (`section: "images"`):**

```json
{
  "section": "images",
  "Image": "nginx:1.25",
  "Size": "187 MB",
  "Created": "2026-03-01 00:00:00"
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Container is running |
| `WARN` | Container is paused or restarting |
| `INFO` | Container is stopped or exited |

---

## compose-health.py

Scans configured directories for Docker Compose projects and checks the current state of each service. Reports any services that are not in a `running` state.

### Syntax

```
python3 tools/docker/compose-health.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path PATH` | From `[docker] compose_paths` | Additional compose project directory to check. Can be repeated. |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Check all configured compose projects:**

```bash
python3 tools/docker/compose-health.py
```

**Add an extra project directory:**

```bash
python3 tools/docker/compose-health.py --path /opt/compose/myapp
```

**JSON output:**

```bash
python3 tools/docker/compose-health.py --json
```

**Show only stopped/failed services:**

```bash
python3 tools/docker/compose-health.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r.get('Status') != 'OK':
        print(f\"[{r['Status']}] {r['Project']}/{r['Service']} - {r['State']}\")
"
```

### Sample Output

```
=========================================
  Docker Compose Health
=========================================

--- monitoring ---
  Service       Image                   State    Ports  Status
  ────────────  ──────────────────────  ───────  ─────  ──────
  prometheus    prom/prometheus:v2.47   running  9090   OK
  grafana       grafana/grafana:10.1    running  3000   OK
  alertmanager  prom/alertmanager:0.26  running  9093   OK

--- registry ---
  Service   Image       State    Ports  Status
  ────────  ──────────  ───────  ─────  ──────
  registry  registry:2  running  5000   OK
  nginx     nginx:1.25  exited   443    WARN
```

### Config Setup

Set your compose project directories in config:

```ini
[docker]
compose_paths =
    /opt/compose/monitoring,
    /opt/compose/registry,
    /opt/compose/gitlab
```

Each directory should contain a `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, or `compose.yaml` file.

### Compose v1 vs v2

The tool tries `docker compose ps --format json` (v2) first. If that fails, it falls back to `docker-compose ps` (v1 standalone binary). If neither is available, the service row shows an error.

To check which version is installed:

```bash
docker compose version          # v2 (plugin)
docker-compose --version        # v1 (standalone)
```

Rocky Linux ships Docker Compose v2 as a Docker plugin by default with `docker-ce`.

### Starting a Stopped Service

If a service shows as `exited`:

```bash
cd /opt/compose/monitoring
docker compose up -d nginx
docker compose logs nginx
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Service is in the `running` state |
| `WARN` | Service is stopped, exited, or in an error state |
| `FAIL` | Could not query the project (compose CLI error) |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All services in all projects are running |
| `2` | One or more services are stopped or exited |
| `1` | Tool error or compose CLI failure |
