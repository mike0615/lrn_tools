#!/usr/bin/env bash
# install.sh — Install or update lrn_tools on this system.
#
# Default install path:  /opt/lrn_tools  (when run as root)
#                        ~/dev/lrn_tools  (when run as non-root)
#
# Override:  LRN_INSTALL_PATH=/custom/path sudo bash install.sh
#
# What it does:
#   1. Optionally copies the repo to LRN_INSTALL_PATH (if running from elsewhere)
#   2. Creates ~/.lrn_tools/ config directory with starter config
#   3. Creates symlinks: /usr/local/bin/lrn-admin and lrn-web
#   4. Installs a systemd unit for the web dashboard (root only)
#
# Usage:
#   sudo bash install.sh                     # root: /opt/lrn_tools + systemd
#   bash install.sh                          # non-root: ~/dev/lrn_tools
#   LRN_INSTALL_PATH=/srv/lrn sudo bash install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() { echo -e "\n${CYAN}── $* ──${NC}"; }

# ── Determine install path ───────────────────────────────────────────────────

if [[ $EUID -eq 0 ]]; then
    INSTALL_PATH="${LRN_INSTALL_PATH:-/opt/lrn_tools}"
    BIN_DIR="/usr/local/bin"
    # Run as the invoking user (SUDO_USER) so service files are correct
    RUN_USER="${SUDO_USER:-root}"
    RUN_HOME=$(getent passwd "${RUN_USER}" | cut -d: -f6)
else
    INSTALL_PATH="${LRN_INSTALL_PATH:-${HOME}/dev/lrn_tools}"
    BIN_DIR="${HOME}/bin"
    RUN_USER="${USER}"
    RUN_HOME="${HOME}"
fi

CONFIG_DIR="${RUN_HOME}/.lrn_tools"
CONFIG_FILE="${CONFIG_DIR}/config.ini"

echo ""
echo -e "${CYAN}lrn_tools installer${NC}"
echo "  Source:      ${SCRIPT_DIR}"
echo "  Install to:  ${INSTALL_PATH}"
echo "  Run as user: ${RUN_USER}"
echo "  Config dir:  ${CONFIG_DIR}"
echo ""

# ── 1. Copy to install path (if source != install path) ─────────────────────

section "Install Path"

if [[ "${SCRIPT_DIR}" != "${INSTALL_PATH}" ]]; then
    if [[ $EUID -ne 0 ]]; then
        warn "Not root — cannot write to ${INSTALL_PATH} if it requires root."
    fi
    info "Copying lrn_tools to ${INSTALL_PATH}..."
    mkdir -p "${INSTALL_PATH}"
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
          "${SCRIPT_DIR}/" "${INSTALL_PATH}/"
    if [[ $EUID -eq 0 && -n "${SUDO_USER:-}" ]]; then
        chown -R "${SUDO_USER}:${SUDO_USER}" "${INSTALL_PATH}" 2>/dev/null || true
    fi
    info "Copied to ${INSTALL_PATH}"
else
    info "Already at install path: ${INSTALL_PATH}"
fi

# ── 2. Config scaffold ───────────────────────────────────────────────────────

section "Config"

mkdir -p "${CONFIG_DIR}"
chmod 700 "${CONFIG_DIR}"

EXAMPLE="${INSTALL_PATH}/config/lrn_tools.conf.example"
if [[ ! -f "${CONFIG_FILE}" ]]; then
    if [[ -f "${EXAMPLE}" ]]; then
        cp "${EXAMPLE}" "${CONFIG_FILE}"
        info "Starter config written to: ${CONFIG_FILE}"
    else
        # Create a minimal default config
        cat > "${CONFIG_FILE}" <<CONF
[site]
name = LRN Admin

[web]
host = 0.0.0.0
port = 5000

[tools]
timeout = 120
CONF
        info "Minimal config written to: ${CONFIG_FILE}"
    fi
    warn "Edit ${CONFIG_FILE} with your site-specific settings."
else
    info "Config already exists: ${CONFIG_FILE} (not overwritten)"
fi

# ── 3. Python check ──────────────────────────────────────────────────────────

section "Python"

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

# ── 4. Flask check ───────────────────────────────────────────────────────────

if ! "${PYTHON}" -c "import flask" 2>/dev/null; then
    warn "Flask not found — web dashboard will not start without it."
    warn "Install: dnf install python3-flask"
else
    info "Flask: $("${PYTHON}" -c "import flask; print(flask.__version__)")"
fi

# ── 5. Symlinks ──────────────────────────────────────────────────────────────

section "Symlinks"

if [[ $EUID -ne 0 ]]; then
    mkdir -p "${BIN_DIR}"
    warn "Not root — symlinks created in ${BIN_DIR} (add to PATH if needed)"
fi

chmod +x "${INSTALL_PATH}/tui/lrn_admin.py" 2>/dev/null || true
chmod +x "${INSTALL_PATH}/web/app.py"        2>/dev/null || true
find "${INSTALL_PATH}/tools" -name "*.py" -exec chmod +x {} \; 2>/dev/null || true

ln -sf "${INSTALL_PATH}/tui/lrn_admin.py" "${BIN_DIR}/lrn-admin"
ln -sf "${INSTALL_PATH}/web/app.py"        "${BIN_DIR}/lrn-web"
info "Symlink: ${BIN_DIR}/lrn-admin  ->  ${INSTALL_PATH}/tui/lrn_admin.py"
info "Symlink: ${BIN_DIR}/lrn-web    ->  ${INSTALL_PATH}/web/app.py"

# ── 6. Systemd unit (root only) ──────────────────────────────────────────────

if [[ $EUID -eq 0 ]]; then
    section "Systemd"
    UNIT_FILE="/etc/systemd/system/lrn-web.service"

    cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=LRN Tools Web Dashboard
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${INSTALL_PATH}
ExecStart=${PYTHON} ${INSTALL_PATH}/web/app.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    info "Systemd unit written: ${UNIT_FILE}"

    if systemctl is-active --quiet lrn-web 2>/dev/null; then
        systemctl restart lrn-web
        info "Service restarted: lrn-web"
    else
        info "To enable and start:  systemctl enable --now lrn-web"
    fi
fi

# ── 7. Hosts file ────────────────────────────────────────────────────────────

HOSTS_FILE="${CONFIG_DIR}/hosts.json"
if [[ ! -f "${HOSTS_FILE}" ]]; then
    echo '[]' > "${HOSTS_FILE}"
    chmod 600 "${HOSTS_FILE}"
    info "Created empty hosts file: ${HOSTS_FILE}"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   lrn_tools installation complete!   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "  Install path: ${INSTALL_PATH}"
echo "  Config file:  ${CONFIG_FILE}"
echo "  Hosts file:   ${HOSTS_FILE}"
echo ""
echo "  TUI console:    lrn-admin"
echo "  Web dashboard:  lrn-web   (then open http://localhost:5000)"
echo ""
if [[ $EUID -ne 0 ]]; then
    echo -e "${YELLOW}  Tip: run as root for systemd service and /opt install path${NC}"
fi
echo ""
