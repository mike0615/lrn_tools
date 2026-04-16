lrn-tools 2.3.0 Air-Gap Bundle
================================

Contents
--------
  lrn-tools-2.3.0-1.el9.x86_64.rpm  — Main package (Flask vendored inside)
  install.sh                          — One-shot installer
  optional-deps/                      — Place rsync + sshpass RPMs here (see below)
  README.txt                          — This file

Requirements
------------
  - Rocky Linux 9.x x86_64 (or RHEL 9 compatible)
  - python3          — included in Rocky 9 base install
  - openssh-clients  — included in Rocky 9 base install

Optional (for full functionality)
----------------------------------
  rsync   — required for the Deploy button (push lrn_tools to remote hosts)
  sshpass — required for password-based SSH auth on remote hosts

  To bundle these, run on a connected Rocky 9 machine:
    dnf download rsync sshpass --resolve --destdir=optional-deps/

  Place the downloaded RPMs in optional-deps/ before running install.sh.

Install
-------
  sudo bash install.sh

  # Or manually:
  sudo dnf install -y lrn-tools-2.3.0-1.el9.x86_64.rpm

Post-install
------------
  # Enable and start the web dashboard (port 5000):
  systemctl enable --now lrn-web

  # Open firewall if needed:
  firewall-cmd --add-port=5000/tcp --permanent && firewall-cmd --reload

  # TUI console:
  lrn-admin

  # Config file (auto-created on first install):
  ~/.lrn_tools/config.ini

  # Saved host profiles:
  ~/.lrn_tools/hosts.json

What's included in the RPM
---------------------------
  /opt/lrn_tools/           — All tool scripts, web dashboard, TUI
  /opt/lrn_tools/vendor/    — Flask 3.1.3 + deps (no internet needed)
  /usr/local/bin/lrn-web    — Web dashboard launcher
  /usr/local/bin/lrn-admin  — TUI console launcher
  /usr/lib/systemd/system/lrn-web.service
  /etc/lrn_tools/config.ini.example

To rebuild this RPM from source
--------------------------------
  # On a connected Rocky 9 machine:
  dnf install -y rpm-build python3-pip git
  git clone https://github.com/mike0615/lrn_tools.git
  cd lrn_tools
  bash packaging/build-rpm.sh
