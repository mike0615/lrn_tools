# TUI Console (`lrn-admin`)

The `lrn-admin` command launches a two-pane ncurses text console for browsing and running all lrn_tools from the terminal. No mouse required.

---

## Starting the TUI

```bash
lrn-admin
```

Or directly:

```bash
python3 ~/dev/lrn_tools/tui/lrn_admin.py
```

Works over SSH. Requires a terminal that supports ANSI color (virtually any modern terminal emulator, PuTTY, or tmux pane).

---

## Screen Layout

```
┌──────────────────────┬───────────────────────────────────────────────┐
│     Categories       │                    Tools                       │
│                      │                                                 │
│  > DNS               │  > Generate Reverse Zones                      │
│    FreeIPA           │    DNS Query Test                               │
│    Certificates      │    Zone Consistency Check                       │
│    System            │                                                 │
│    KVM               │                                                 │
│    DNF               │                                                 │
│    Docker            │                                                 │
│    Network           │                                                 │
│    Logs              │                                                 │
├──────────────────────┴───────────────────────────────────────────────┤
│                        Output                                          │
│                                                                        │
│  Running: tools/dns/dns-query-test.py                                  │
│  ─────────────────────────────────────                                 │
│    Name         Type  Server        Answer          Status             │
│    ──────────── ────  ──────────── ─────────────── ──────             │
│    lrn.local    SOA   192.168.1.10  ns1.lrn.local.  OK                │
│                                                                        │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
 LRN Admin  |  Tab=switch  Enter=run  a=run+args  ?=help  q=quit    idle
```

**Left pane** — category list. Navigate with arrow keys.  
**Right pane** — tools in the selected category. Switch to it with Tab.  
**Bottom panel** — live output from the last tool run. Scrollable while a tool is running.  
**Status bar** — key hint strip and current tool run status.

---

## Keyboard Reference

### Navigation

| Key | Action |
|-----|--------|
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `→` / `Tab` | Move focus to right pane (tools) |
| `←` / `Tab` (from tools) | Move focus back to categories |
| `Enter` | In categories: switch to tool pane. In tools: run selected tool. |

### Running Tools

| Key | Action |
|-----|--------|
| `Enter` | Run the selected tool with no extra arguments |
| `r` | Same as Enter — run selected tool |
| `a` | Prompt for extra arguments, then run |

When you press `a`, a small dialog appears at the center of the screen:

```
┌──────────── Run: DNS Query Test ────────────────────────────┐
│ Test forward/reverse/SRV queries against DNS servers        │
│ Extra args (Enter to run, ESC to cancel):                   │
│ --name ipa01.lrn.local --type A                             │
└─────────────────────────────────────────────────────────────┘
```

Type any flags the tool accepts (see each tool's docs), then press Enter. Press ESC to cancel.

### Output Panel

| Key | Action |
|-----|--------|
| `Page Up` | Scroll output up 10 lines |
| `Page Down` | Scroll output down 10 lines |
| `Home` | Jump to top of output |
| `End` | Jump to bottom of output |

The output panel auto-scrolls to the bottom as a tool produces new lines. Use `Home` / `Page Up` to review earlier output while a tool is still running.

### Other

| Key | Action |
|-----|--------|
| `?` | Show key binding help overlay |
| `q` / `ESC` | If in tool pane: go back to category pane. If in category pane: quit. |

---

## Output Colorization

The output panel applies basic color hints to lines containing known keywords:

| Color | Triggered by |
|-------|-------------|
| Green | `[OK]`, `PASS` |
| Yellow | `[WARN]`, `WARN` |
| Red | `[ERR]`, `[CRIT]`, `FAIL`, `ERROR` |

This is pattern-matched on the raw output, so it works for all tools regardless of their internal structure.

---

## Running Tools with Arguments via `a`

The argument string is split on spaces and appended to the tool's command. Examples:

| Tool | Argument string | What runs |
|------|----------------|-----------|
| `dns-query-test` | `--name ipa01.lrn.local --type A` | DNS A lookup for ipa01 |
| `service-status` | `--service named,chronyd` | Check specific services |
| `journal-errors` | `--hours 48 --unit named` | 48h errors for named only |
| `cert-expiry-check` | `--days 60` | Warn at 60 days |
| `gen-reverse-zones` | `/var/named/db.lrn.local --dry-run` | Preview reverse zones |

---

## Behavior Notes

- Tools run as a subprocess of the TUI. Their output streams line-by-line into the output panel.
- The TUI does **not** pass `--json` to tools — it shows the human-readable colored output directly.
- You can navigate the category/tool panes while a tool is still running. The output panel continues to update.
- Running a new tool while one is still running starts a new subprocess. The old one continues but its output is replaced in the panel.
- Terminal resize is handled dynamically — the layout reflows on resize.

---

## Troubleshooting the TUI

| Issue | Fix |
|-------|-----|
| Garbled display | Your terminal may not support UTF-8. Try `export LANG=en_US.UTF-8` |
| Colors look wrong | Try `export TERM=xterm-256color` |
| TUI exits immediately | Python may have raised an exception — run the tool directly to see the error: `python3 tools/system/sysinfo.py` |
| `lrn-admin` not found | Check `~/bin` is in `$PATH` (non-root install) or `/usr/local/bin` (root install) |
