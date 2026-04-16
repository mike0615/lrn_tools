%global debug_package %{nil}

Name:           lrn-tools
Version:        2.3.0
Release:        1%{?dist}
Summary:        LRN Admin Tools Suite for Rocky/RHEL sysadmins
License:        MIT
URL:            https://github.com/mike0615/lrn_tools

Source0:        %{name}-%{version}.tar.gz
Source1:        %{name}-vendor-%{version}.tar.gz

BuildRequires:  python3
BuildRequires:  python3-pip

Requires:       python3
Requires:       openssh-clients

Recommends:     rsync
Recommends:     sshpass

%description
LRN Tools is a sysadmin toolkit for Rocky/RHEL 9 environments featuring:

 - 27+ tools: DNS, FreeIPA, certs, system, KVM, DNF, Docker, network, logs
 - Web dashboard (Flask) with live output streaming and remote SSH execution
 - ncurses TUI console
 - Saved SSH host profiles with key and password auth
 - One-click rsync deployment to remote hosts
 - Subnet calculator, SSH key generator, password hasher, audit log viewer,
   software inventory, and system status report

Flask and its dependencies are vendored inside the package.
No internet or extra repos required on the target system.

%prep
%setup -q -n %{name}-%{version}
tar -xzf %{SOURCE1}

%build
# pure Python, nothing to compile

%install
rm -rf %{buildroot}

install -d %{buildroot}/opt/lrn_tools
cp -r lib tools tui web %{buildroot}/opt/lrn_tools/
test -d config && cp -r config %{buildroot}/opt/lrn_tools/ || true
test -f README.md && install -m 644 README.md %{buildroot}/opt/lrn_tools/ || true

install -d %{buildroot}/opt/lrn_tools/vendor
pip3 install \
    --no-index \
    --find-links vendor-wheels/ \
    --target %{buildroot}/opt/lrn_tools/vendor \
    flask

install -d %{buildroot}/usr/local/bin

cat > %{buildroot}/usr/local/bin/lrn-web << 'ENDWRAPPER'
#!/usr/bin/env bash
export PYTHONPATH=/opt/lrn_tools/vendor${PYTHONPATH:+:$PYTHONPATH}
exec python3 /opt/lrn_tools/web/app.py "$@"
ENDWRAPPER
chmod 755 %{buildroot}/usr/local/bin/lrn-web

cat > %{buildroot}/usr/local/bin/lrn-admin << 'ENDWRAPPER'
#!/usr/bin/env bash
export PYTHONPATH=/opt/lrn_tools/vendor${PYTHONPATH:+:$PYTHONPATH}
exec python3 /opt/lrn_tools/tui/lrn_admin.py "$@"
ENDWRAPPER
chmod 755 %{buildroot}/usr/local/bin/lrn-admin

install -d %{buildroot}/usr/lib/systemd/system
cat > %{buildroot}/usr/lib/systemd/system/lrn-web.service << 'ENDUNIT'
[Unit]
Description=LRN Tools Web Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lrn_tools
ExecStart=/usr/local/bin/lrn-web --host 0.0.0.0 --port 5000
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/lrn_tools/vendor
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
ENDUNIT

install -d %{buildroot}/etc/lrn_tools
cat > %{buildroot}/etc/lrn_tools/config.ini.example << 'ENDCONF'
[site]
name = LRN Admin

[web]
host = 0.0.0.0
port = 5000
debug = false

[tools]
timeout = 120
ENDCONF

%post
CONFIG_DIR="${HOME:-/root}/.lrn_tools"
CONFIG_FILE="$CONFIG_DIR/config.ini"
HOSTS_FILE="$CONFIG_DIR/hosts.json"

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    cp /etc/lrn_tools/config.ini.example "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
fi

if [ ! -f "$HOSTS_FILE" ]; then
    echo '[]' > "$HOSTS_FILE"
    chmod 600 "$HOSTS_FILE"
fi

systemctl daemon-reload >/dev/null 2>&1 || true

echo ""
echo "  lrn-tools %{version} installed."
echo ""
echo "  Config : $CONFIG_FILE"
echo "  Hosts  : $HOSTS_FILE"
echo ""
echo "  Enable web dashboard : systemctl enable --now lrn-web"
echo "  TUI console          : lrn-admin"
echo "  Manual web start     : lrn-web  (then open http://localhost:5000)"
echo ""

%preun
if [ $1 -eq 0 ]; then
    systemctl stop    lrn-web >/dev/null 2>&1 || true
    systemctl disable lrn-web >/dev/null 2>&1 || true
fi

%postun
systemctl daemon-reload >/dev/null 2>&1 || true

%files
%defattr(-,root,root,-)
/opt/lrn_tools/
/usr/local/bin/lrn-web
/usr/local/bin/lrn-admin
/usr/lib/systemd/system/lrn-web.service
/etc/lrn_tools/

%changelog
* Thu Apr 16 2026 Mike Anderson <admin@lrn.local> - 2.3.0-1
- v2.3.0: 6 new tools, /opt install path, one-click rsync deploy
- v2.2.0: Remote SSH host execution, saved host profiles, streaming SSE
- v2.1.0: LRN Man mascot, light/dark mode, 200+ contextual tips
- v2.0.0: Full admin toolkit (27 tools, TUI, Flask web dashboard)
- v1.0.0: Initial release
