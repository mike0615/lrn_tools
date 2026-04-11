# Installation & Setup

## Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.6+ | Standard library only for all CLI tools |
| Flask | any | Web dashboard only — `dnf install python3-flask` |
| bind-utils | any | `dns-query-test.py` uses `dig` — `dnf install bind-utils` |
| libvirt-client | any | KVM tools use `virsh` — `dnf install libvirt-client` |
| Docker / Podman | any | Docker tools — `dnf install docker-ce` or `podman-docker` |
| openssl | any | Certificate tools — already present on Rocky Linux |

All tools degrade gracefully when optional dependencies are absent — they print an installation hint and exit cleanly rather than crashing.

---

## Install

### 1. Clone the Repository

```bash
# Recommended location
cd ~/dev
git clone https://github.com/mike0615/lrn_tools.git
cd lrn_tools
```

### 2. Run the Installer

```bash
# Non-root: symlinks go to ~/bin
bash install.sh

# Root: symlinks go to /usr/local/bin + systemd unit for lrn-web
sudo bash install.sh
```

What `install.sh` does:
- Creates `~/.lrn_tools/` directory
- Copies the starter config to `~/.lrn_tools/config.ini` (only if it does not already exist)
- Creates `lrn-admin` symlink (TUI launcher)
- Creates `lrn-web` symlink (web dashboard)
- Makes all tool scripts executable
- Checks for Flask and prints install hint if missing
- If run as root: writes `/etc/systemd/system/lrn-web.service` and runs `systemctl daemon-reload`

The installer is idempotent — safe to re-run after updates.

### 3. Add `~/bin` to PATH (non-root only)

If not already set:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Edit the Config

```bash
vi ~/.lrn_tools/config.ini
```

At minimum, set:
- `[ipa] server` — your FreeIPA server hostname
- `[dns] servers` — your BIND nameserver IP(s)
- `[dns] domain` — your DNS domain (e.g., `lrn.local`)
- `[services] critical_services` — systemd units you care about
- `[network] check_hosts` — hosts to ping/connect during connectivity checks

See [Configuration Reference](config-reference.md) for every option.

### 5. Verify

```bash
# Run a tool directly
python3 ~/dev/lrn_tools/tools/system/sysinfo.py

# Launch the TUI
lrn-admin

# Start the web dashboard
lrn-web
# Open http://127.0.0.1:5000
```

---

## Upgrading

```bash
cd ~/dev/lrn_tools
git pull
bash install.sh     # re-run to pick up new symlinks or config keys
```

Your `~/.lrn_tools/config.ini` is never overwritten by the installer. If new config keys are added in an upgrade, compare against `config/lrn_tools.conf.example` and add them manually.

---

## Air-Gapped Installation

For systems without internet access:

```bash
# On an internet-connected machine
git clone https://github.com/mike0615/lrn_tools.git
tar czf lrn_tools.tar.gz lrn_tools/

# Transfer to air-gapped system (USB, SCP over jump host, etc.)
# then on the air-gapped system:
tar xzf lrn_tools.tar.gz
cd lrn_tools
bash install.sh
```

Flask for the web dashboard is available from Rocky Linux's standard repos (no internet needed after initial `dnf` sync):

```bash
dnf install python3-flask
```

If DNF repos are also offline, Flask can be bundled as an RPM on the transfer medium.

---

## Running as a Service (Web Dashboard)

If `install.sh` was run as root, the systemd unit is already written:

```bash
sudo systemctl enable --now lrn-web
sudo systemctl status lrn-web
```

To change the bind address or port, edit the config and restart:

```bash
vi ~/.lrn_tools/config.ini   # set [web] host and [web] port
sudo systemctl restart lrn-web
```

To expose the dashboard on your LAN (use behind a firewall):

```ini
[web]
host = 0.0.0.0
port = 5000
```

Then open the firewall port:

```bash
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

---

## Directory Reference

| Path | Purpose |
|------|---------|
| `~/dev/lrn_tools/` | Project root |
| `~/.lrn_tools/config.ini` | Site configuration |
| `~/dev/lrn_tools/lib/` | Shared Python library |
| `~/dev/lrn_tools/tools/` | All tool scripts |
| `~/dev/lrn_tools/tui/lrn_admin.py` | TUI entry point |
| `~/dev/lrn_tools/web/app.py` | Web dashboard entry point |
| `~/dev/lrn_tools/config/lrn_tools.conf.example` | Config template |
| `/usr/local/bin/lrn-admin` | Symlink to TUI (root install) |
| `/usr/local/bin/lrn-web` | Symlink to web app (root install) |
| `/etc/systemd/system/lrn-web.service` | Systemd unit (root install only) |
