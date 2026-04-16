#!/usr/bin/env bash
# install.sh — Install lrn-tools on an air-gapped Rocky 9.7 system
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "\n${GREEN}lrn-tools air-gapped installer${NC}\n"

# Install optional deps from bundled RPMs if present
OPT_DIR="${SCRIPT_DIR}/optional-deps"
if ls "${OPT_DIR}"/*.rpm &>/dev/null 2>&1; then
    echo "Installing optional deps from ${OPT_DIR}..."
    dnf install -y "${OPT_DIR}"/*.rpm
fi

# Install the main package
RPM=$(ls "${SCRIPT_DIR}"/lrn-tools-*.rpm | head -1)
echo "Installing ${RPM}..."
dnf install -y "${RPM}"

IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   lrn-tools installed successfully!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Start the web dashboard:"
echo "    systemctl enable --now lrn-web"
echo ""
echo -e "  ${YELLOW}Then open: http://${IP}:5000${NC}"
echo ""
