# KVM Tools

Tools for inventorying and reporting on KVM virtual machines managed by libvirt.

| Tool | Script | Requires |
|------|--------|----------|
| VM List | `tools/kvm/vm-list.py` | `virsh` (`dnf install libvirt-client`) |
| Snapshot Report | `tools/kvm/vm-snapshot-report.py` | `virsh` (`dnf install libvirt-client`) |

### Prerequisites

```bash
dnf install libvirt-client
```

The user running these tools must be able to connect to libvirtd. For local system VMs:

```bash
# Check access
virsh -c qemu:///system list --all
```

If this fails as a non-root user, add yourself to the `libvirt` group:

```bash
sudo usermod -aG libvirt $USER
# Log out and back in
```

The `libvirt_uri` in config defaults to `qemu:///system`. For remote hypervisors:

```ini
[kvm]
libvirt_uri = qemu+ssh://root@hypervisor.lrn.local/system
```

---

## vm-list.py

Lists all KVM guest VMs with their operational state, resource allocation, network interface configuration, and autostart setting.

### Syntax

```
python3 tools/kvm/vm-list.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--running` | off | Show only running VMs (exclude shut-off, paused, etc.) |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**List all VMs:**

```bash
python3 tools/kvm/vm-list.py
```

**List only running VMs:**

```bash
python3 tools/kvm/vm-list.py --running
```

**JSON output:**

```bash
python3 tools/kvm/vm-list.py --json
```

**Count running VMs:**

```bash
python3 tools/kvm/vm-list.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
running = [r for r in d['records'] if r['State'] == 'running']
print(f\"{len(running)} of {len(d['records'])} VMs are running\")
"
```

**List VMs not set to autostart:**

```bash
python3 tools/kvm/vm-list.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['records']:
    if r.get('Autostart','').lower() == 'disable':
        print(r['VM Name'], '- autostart OFF')
"
```

### Sample Output

```
=========================================
  KVM Virtual Machine Inventory
=========================================

  Hypervisor: qemu:///system   Total VMs: 6

  VM Name          State    vCPUs  RAM         Autostart  Interfaces        Status
  ───────────────  ───────  ─────  ──────────  ─────────  ────────────────  ──────
  ipa01            running  4      4194304 KiB enable     vnet0(br-mgmt)    OK
  ipa02            running  4      4194304 KiB enable     vnet1(br-mgmt)    OK
  ns1              running  2      2097152 KiB enable     vnet2(br-mgmt)    OK
  webserver        running  4      8388608 KiB enable     vnet3(br-app)     OK
  devbox           shut off 4      4194304 KiB disable    vnet4(br-mgmt)    INFO
  old-test         shut off 2      2097152 KiB disable    -                 INFO
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | VM is running |
| `WARN` | VM is paused |
| `INFO` | VM is shut off or in another non-running state |

### Understanding RAM Values

The `RAM` column shows the **maximum memory** configured for the VM in KiB (as reported by `virsh dominfo`). This is the allocated ceiling, not the currently used RAM. To see actual memory consumption, check `virsh dommemstat <vmname>`.

---

## vm-snapshot-report.py

Lists all snapshots for every VM and flags those older than a configured threshold as stale. Stale snapshots consume disk space and can indicate forgotten or abandoned checkpoint states.

### Syntax

```
python3 tools/kvm/vm-snapshot-report.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--days N` | From `[kvm] snapshot_stale_days` (default: 14) | Number of days after which a snapshot is considered stale |
| `--json` | off | Emit JSON output |
| `--no-color` | off | Disable ANSI color |
| `--config PATH` | `~/.lrn_tools/config.ini` | Config file path |

### Examples

**Report all snapshots (14-day stale threshold from config):**

```bash
python3 tools/kvm/vm-snapshot-report.py
```

**Use a 30-day stale threshold:**

```bash
python3 tools/kvm/vm-snapshot-report.py --days 30
```

**JSON output:**

```bash
python3 tools/kvm/vm-snapshot-report.py --json
```

**List only stale snapshots:**

```bash
python3 tools/kvm/vm-snapshot-report.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
stale = [r for r in d['records'] if r.get('Stale') == 'YES']
if not stale:
    print('No stale snapshots.')
else:
    print(f'{len(stale)} stale snapshot(s):')
    for r in stale:
        print(f\"  {r['VM']} / {r['Snapshot']} — {r['Days Old']} days old\")
"
```

**Get VM names that have stale snapshots:**

```bash
python3 tools/kvm/vm-snapshot-report.py --json | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
vms = {r['VM'] for r in d['records'] if r.get('Stale') == 'YES'}
for v in sorted(vms): print(v)
"
```

### Sample Output

```
====================================
  KVM Snapshot Report
====================================

  Stale threshold: 14 days

  VM         Snapshot     Created                    Days Old  Stale  Status
  ─────────  ───────────  ─────────────────────────  ────────  ─────  ──────
  ipa01      pre-upgrade  2026-04-01 09:00:00 +0000  10        no     OK
  ipa02      pre-upgrade  2026-03-01 09:00:00 +0000  41        YES    WARN
  devbox     test-snap-1  2026-01-15 14:30:00 +0000  86        YES    WARN
  devbox     test-snap-2  2026-04-08 11:00:00 +0000  3         no     OK
```

### Status Values

| Status | Meaning |
|--------|---------|
| `OK` | Snapshot is newer than the stale threshold |
| `WARN` | Snapshot is older than the stale threshold |

### Deleting Stale Snapshots

After reviewing the report:

```bash
# Delete a specific snapshot
virsh snapshot-delete <vm-name> <snapshot-name>

# Example
virsh snapshot-delete ipa02 pre-upgrade
virsh snapshot-delete devbox test-snap-1

# Verify
virsh snapshot-list ipa02
```

### Snapshot Performance Note

For environments with many VMs and many snapshots, the report may take 30-60 seconds to complete because it calls `virsh snapshot-info` for each snapshot individually. This is a libvirt API limitation. The tool applies no timeout per query to avoid false failures on slow storage.

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No stale snapshots found |
| `2` | One or more stale snapshots detected |
| `1` | Tool error (virsh not found or libvirt connection failed) |
