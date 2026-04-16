#!/usr/bin/env bash
# packaging/build-rpm.sh — Build the lrn-tools RPM for air-gapped Rocky 9.7
#
# Run this on a connected Rocky 9 machine that has:
#   dnf install -y rpm-build python3-pip
#
# What this script does:
#   1. Creates a git archive of the repo as Source0
#   2. Downloads Flask + deps as binary wheels from PyPI (Source1)
#   3. Runs rpmbuild -bb to produce the RPM
#   4. Assembles a self-contained air-gap bundle directory
#
# Output:
#   ~/rpmbuild/RPMS/noarch/lrn-tools-2.3.0-1.el9.noarch.rpm
#   packaging/lrn-tools-airgap-2.3.0/   ← copy this entire dir to the air-gapped host
#
# Deploy to air-gapped host:
#   scp -r packaging/lrn-tools-airgap-2.3.0/ root@TARGET:/tmp/
#   ssh root@TARGET 'bash /tmp/lrn-tools-airgap-2.3.0/install.sh'

set -euo pipefail

VERSION="2.3.0"
PKG="lrn-tools"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STAGING="${SCRIPT_DIR}/staging"
VENDOR_STAGING="${STAGING}/vendor-wheels"
BUILD_ROOT="${HOME}/rpmbuild"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
section() { echo -e "\n${CYAN}── $* ──${NC}"; }

echo ""
echo -e "${CYAN}lrn-tools RPM builder v${VERSION}${NC}"
echo "  Repo     : ${REPO_ROOT}"
echo "  Build    : ${BUILD_ROOT}"
echo "  Staging  : ${STAGING}"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────────────

section "Pre-flight checks"

for cmd in rpmbuild python3 pip3 git tar; do
    if ! command -v "$cmd" &>/dev/null; then
        error "$cmd not found. Install missing tools:  dnf install -y rpm-build python3-pip git"
    fi
    info "  $cmd: $(command -v $cmd)"
done

# ── rpmbuild tree ────────────────────────────────────────────────────────────

section "Setting up rpmbuild tree"
mkdir -p "${BUILD_ROOT}"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
info "rpmbuild tree ready at ${BUILD_ROOT}"

# ── Source0: git archive of the repo ─────────────────────────────────────────

section "Creating source tarball (Source0)"
SOURCE0="${BUILD_ROOT}/SOURCES/${PKG}-${VERSION}.tar.gz"

git -C "${REPO_ROOT}" archive \
    --format=tar.gz \
    --prefix="${PKG}-${VERSION}/" \
    HEAD > "${SOURCE0}"

SIZE=$(du -sh "${SOURCE0}" | cut -f1)
info "Source0: ${SOURCE0}  (${SIZE})"

# ── Source1: vendor wheels ────────────────────────────────────────────────────

section "Downloading Flask vendor wheels (Source1)"
rm -rf "${VENDOR_STAGING}"
mkdir -p "${VENDOR_STAGING}"

info "Downloading Flask and dependencies from PyPI..."

# Download binary wheels for Python 3.9 / manylinux (Rocky 9 compatible).
# Fall back to platform-agnostic if targeted download fails.
pip3 download flask \
    --dest "${VENDOR_STAGING}" \
    --prefer-binary \
    --python-version 3.9 \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    2>/dev/null \
|| {
    warn "Targeted wheel download failed — retrying without platform filter"
    pip3 download flask \
        --dest "${VENDOR_STAGING}" \
        --prefer-binary
}

echo ""
info "Downloaded wheels:"
ls "${VENDOR_STAGING}" | sed 's/^/    /'

SOURCE1="${BUILD_ROOT}/SOURCES/${PKG}-vendor-${VERSION}.tar.gz"
tar -czf "${SOURCE1}" -C "${STAGING}" vendor-wheels/
SIZE=$(du -sh "${SOURCE1}" | cut -f1)
info "Source1: ${SOURCE1}  (${SIZE})"

# ── Spec file ────────────────────────────────────────────────────────────────

section "Installing spec file"
cp "${SCRIPT_DIR}/lrn_tools.spec" "${BUILD_ROOT}/SPECS/"
info "Spec: ${BUILD_ROOT}/SPECS/lrn_tools.spec"

# ── Build RPM ─────────────────────────────────────────────────────────────────

section "Building RPM"
rpmbuild -bb \
    --define "_topdir ${BUILD_ROOT}" \
    "${BUILD_ROOT}/SPECS/lrn_tools.spec"

RPM_FILE=$(find "${BUILD_ROOT}/RPMS" -name "${PKG}-${VERSION}*.rpm" | sort | tail -1)
RPM_SIZE=$(du -sh "${RPM_FILE}" | cut -f1)
info "RPM built: ${RPM_FILE}  (${RPM_SIZE})"

# ── Air-gap bundle ────────────────────────────────────────────────────────────

section "Assembling air-gap bundle"
BUNDLE_DIR="${SCRIPT_DIR}/${PKG}-airgap-${VERSION}"
rm -rf "${BUNDLE_DIR}"
mkdir -p "${BUNDLE_DIR}/optional-deps"

# Main RPM
cp "${RPM_FILE}" "${BUNDLE_DIR}/"

# install.sh for the air-gapped target
cat > "${BUNDLE_DIR}/install.sh" << 'INSTALL'
#!/usr/bin/env bash
# install.sh — Install lrn-tools on an air-gapped Rocky 9.7 system
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "\n${GREEN}lrn-tools air-gapped installer${NC}\n"

# Install optional deps from bundled RPMs if present
OPT_DIR="${SCRIPT_DIR}/optional-deps"
if ls "${OPT_DIR}"/*.rpm &>/dev/null 2>&1; then
    echo "Installing optional deps..."
    dnf install -y "${OPT_DIR}"/*.rpm
fi

# Install the main package
RPM=$(ls "${SCRIPT_DIR}"/lrn-tools-*.rpm | head -1)
echo "Installing ${RPM}..."
dnf install -y "${RPM}"

# Get primary IP for the post-install message
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
INSTALL
chmod +x "${BUNDLE_DIR}/install.sh"

# README for the bundle
cat > "${BUNDLE_DIR}/README.txt" << 'README'
lrn-tools Air-Gap Bundle
========================

Contents
--------
  lrn-tools-2.3.0-1.el9.noarch.rpm  — Main package (includes vendored Flask)
  install.sh                          — One-shot installer
  optional-deps/                      — Place rsync + sshpass RPMs here (see below)
  README.txt                          — This file

Requirements
------------
  - Rocky Linux 9.x (or RHEL 9 compatible)
  - python3                (included in Rocky 9 base)
  - openssh-clients        (included in Rocky 9 base)

Optional (for full functionality)
----------------------------------
  rsync   — required for the Deploy button (push lrn_tools to remote hosts)
  sshpass — required for password-based SSH auth on remote hosts

  To bundle these for air-gapped install, run on a connected Rocky 9 machine:
    dnf download rsync sshpass --resolve --destdir=optional-deps/

  Place the downloaded RPMs in the optional-deps/ directory, then re-run install.sh.

Install
-------
  # Copy this entire directory to the target host, then:
  sudo bash install.sh

  # Or manual install:
  sudo dnf install -y lrn-tools-2.3.0-1.el9.noarch.rpm

Post-install
------------
  # Enable and start the web dashboard:
  systemctl enable --now lrn-web

  # TUI console:
  lrn-admin

  # Config file (created automatically on first install):
  ~/.lrn_tools/config.ini

  # Saved host profiles:
  ~/.lrn_tools/hosts.json
README

BUNDLE_SIZE=$(du -sh "${BUNDLE_DIR}" | cut -f1)
info "Bundle: ${BUNDLE_DIR}/  (${BUNDLE_SIZE})"
ls -lh "${BUNDLE_DIR}/"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Build complete!                            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  RPM    : ${RPM_FILE}"
echo "  Bundle : ${BUNDLE_DIR}/"
echo ""
echo "  Deploy to air-gapped host:"
echo "    scp -r ${BUNDLE_DIR}/ root@TARGET:/tmp/"
echo "    ssh root@TARGET 'bash /tmp/${PKG}-airgap-${VERSION}/install.sh'"
echo ""
