#!/usr/bin/env bash
# install.sh — Set up lrn_tools on this system.
#
# What it does:
#   1. Creates ~/.lrn_tools/ config directory with starter config
#   2. Creates symlinks in /usr/local/bin for lrn-admin and lrn-web
#   3. Optionally installs a systemd unit for the web dashboard
#
# Usage:
#   bash install.sh              # non-root: symlinks in ~/bin instead
#   sudo bash install.sh         # root: symlinks in /usr/local/bin + systemd unit
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.lrn_tools"
CONFIG_FILE="${CONFIG_DIR}/config.ini"
PYTHON="${PYTHON:-python3}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 1. Config scaffold ───────────────────────────────────────────────────────

info "Creating config directory: ${CONFIG_DIR}"
mkdir -p "${CONFIG_DIR}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    cp "${SCRIPT_DIR}/config/lrn_tools.conf.example" "${CONFIG_FILE}"
    info "Starter config written to: ${CONFIG_FILE}"
    warn "Edit ${CONFIG_FILE} with your site-specific settings before running tools."
else
    info "Config already exists: ${CONFIG_FILE} (not overwritten)"
fi

# ── 2. Python check ──────────────────────────────────────────────────────────

if ! command -v "${PYTHON}" &>/dev/null; then
    error "Python 3 not found. Install with: dnf install python3"
    exit 1
fi

PYVER=$("${PYTHON}" -c 'import sys; print(sys.version_info[:2] >= (3,6))')
if [[ "${PYVER}" != "True" ]]; then
    error "Python 3.6+ required."
    exit 1
fi

info "Python: $("${PYTHON}" --version)"

# ── 3. Symlinks ──────────────────────────────────────────────────────────────

if [[ $EUID -eq 0 ]]; then
    BIN_DIR="/usr/local/bin"
else
    BIN_DIR="${HOME}/bin"
    mkdir -p "${BIN_DIR}"
    warn "Not running as root. Symlinks will be created in ${BIN_DIR}."
    warn "Make sure ${BIN_DIR} is in your PATH."
fi

# lrn-admin (TUI)
ln -sf "${SCRIPT_DIR}/tui/lrn_admin.py" "${BIN_DIR}/lrn-admin"
chmod +x "${SCRIPT_DIR}/tui/lrn_admin.py"
info "Symlink created: ${BIN_DIR}/lrn-admin -> ${SCRIPT_DIR}/tui/lrn_admin.py"

# lrn-web (web dashboard)
ln -sf "${SCRIPT_DIR}/web/app.py" "${BIN_DIR}/lrn-web"
chmod +x "${SCRIPT_DIR}/web/app.py"
info "Symlink created: ${BIN_DIR}/lrn-web -> ${SCRIPT_DIR}/web/app.py"

# Make all tools executable
find "${SCRIPT_DIR}/tools" -name "*.py" -exec chmod +x {} \;
info "Made all tool scripts executable."

# ── 4. Check Flask ───────────────────────────────────────────────────────────

if ! "${PYTHON}" -c "import flask" 2>/dev/null; then
    warn "Flask not found. The web dashboard requires Flask."
    warn "Install with: dnf install python3-flask"
    warn "  (or: pip3 install flask --user)"
else
    info "Flask: $("${PYTHON}" -c "import flask; print(flask.__version__)")"
fi

# ── 5. Systemd unit (root only) ──────────────────────────────────────────────

if [[ $EUID -eq 0 ]]; then
    UNIT_FILE="/etc/systemd/system/lrn-web.service"
    RUN_USER="${SUDO_USER:-root}"

    cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=LRN Tools Web Dashboard
After=network.target

[Service]
Type=simple
User=${RUN_USER}
ExecStart=${PYTHON} ${SCRIPT_DIR}/web/app.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    info "Systemd unit written: ${UNIT_FILE}"
    info "To enable: systemctl enable --now lrn-web"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "  Config file:  ${CONFIG_FILE}"
echo "  TUI console:  lrn-admin"
echo "  Web dashboard: lrn-web  (then open http://127.0.0.1:5000)"
echo ""
echo "  Next: edit ${CONFIG_FILE} with your IPA server, DNS servers, etc."
echo ""
