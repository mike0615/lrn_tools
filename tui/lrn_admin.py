#!/usr/bin/env python3
"""
lrn_admin.py — Text-based admin console for lrn_tools.

Two-pane curses interface:
  Left pane:  category list
  Right pane: tools in selected category
  Bottom:     output viewer for tool runs

Keys:
  Arrow keys / j/k  Navigate
  Tab               Switch pane
  Enter             Select / Run tool
  q / ESC           Quit or go back
  ?                 Help
"""

import curses
import os
import subprocess
import sys
import textwrap
import threading

# Project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.registry import TOOLS, get_categories, get_tools_by_category
from lib.config import load_config


# ---------------------------------------------------------------------------
# Color pairs
# ---------------------------------------------------------------------------
PAIR_NORMAL   = 1
PAIR_SELECTED = 2
PAIR_HEADER   = 3
PAIR_OK       = 4
PAIR_WARN     = 5
PAIR_ERROR    = 6
PAIR_BORDER   = 7
PAIR_DIM      = 8


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(PAIR_NORMAL,   curses.COLOR_WHITE,   -1)
    curses.init_pair(PAIR_SELECTED, curses.COLOR_BLACK,   curses.COLOR_CYAN)
    curses.init_pair(PAIR_HEADER,   curses.COLOR_CYAN,    -1)
    curses.init_pair(PAIR_OK,       curses.COLOR_GREEN,   -1)
    curses.init_pair(PAIR_WARN,     curses.COLOR_YELLOW,  -1)
    curses.init_pair(PAIR_ERROR,    curses.COLOR_RED,     -1)
    curses.init_pair(PAIR_BORDER,   curses.COLOR_CYAN,    -1)
    curses.init_pair(PAIR_DIM,      curses.COLOR_WHITE,   -1)


# ---------------------------------------------------------------------------
# Helper: draw a bordered box
# ---------------------------------------------------------------------------

def draw_box(win, title=''):
    h, w = win.getmaxyx()
    win.attron(curses.color_pair(PAIR_BORDER))
    try:
        win.border()
    except curses.error:
        pass
    if title:
        label = f' {title} '
        x = max(2, (w - len(label)) // 2)
        try:
            win.addstr(0, x, label, curses.color_pair(PAIR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass
    win.attroff(curses.color_pair(PAIR_BORDER))


def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    max_len = max(0, w - x - 1)
    try:
        win.addstr(y, x, text[:max_len], attr)
    except curses.error:
        pass


# ---------------------------------------------------------------------------
# Output viewer — scrollable text panel
# ---------------------------------------------------------------------------

class OutputViewer:
    def __init__(self, win):
        self.win = win
        self.lines = []
        self.scroll_offset = 0
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.lines = []
            self.scroll_offset = 0

    def append(self, text):
        with self.lock:
            for line in text.splitlines():
                self.lines.append(line)
            h = self.win.getmaxyx()[0] - 2
            # Auto-scroll to bottom
            if len(self.lines) > h:
                self.scroll_offset = len(self.lines) - h

    def scroll(self, delta):
        with self.lock:
            h = self.win.getmaxyx()[0] - 2
            max_scroll = max(0, len(self.lines) - h)
            self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + delta))

    def draw(self, title='Output'):
        self.win.erase()
        draw_box(self.win, title)
        h, w = self.win.getmaxyx()
        inner_h = h - 2
        inner_w = w - 2

        with self.lock:
            visible = self.lines[self.scroll_offset: self.scroll_offset + inner_h]
            for i, line in enumerate(visible):
                # Basic color hints
                attr = curses.color_pair(PAIR_NORMAL)
                low = line.lower()
                if '[ok]' in low or 'pass' in low:
                    attr = curses.color_pair(PAIR_OK)
                elif '[warn]' in low or 'warn' in low:
                    attr = curses.color_pair(PAIR_WARN)
                elif '[err]' in low or '[crit]' in low or 'fail' in low or 'error' in low:
                    attr = curses.color_pair(PAIR_ERROR)
                safe_addstr(self.win, i + 1, 1, line[:inner_w], attr)

            # Scroll indicator
            total = len(self.lines)
            if total > inner_h:
                pct = int((self.scroll_offset / max(1, total - inner_h)) * 100)
                indicator = f' {pct}% ({self.scroll_offset + 1}-{min(total, self.scroll_offset + inner_h)}/{total}) ↑↓ scroll '
                safe_addstr(self.win, h - 1, max(1, w - len(indicator) - 1),
                             indicator, curses.color_pair(PAIR_DIM))
        self.win.noutrefresh()


# ---------------------------------------------------------------------------
# Menu pane
# ---------------------------------------------------------------------------

class MenuPane:
    def __init__(self, win, items, title=''):
        self.win    = win
        self.items  = items
        self.title  = title
        self.cursor = 0
        self.offset = 0
        self.active = False

    def set_items(self, items):
        self.items  = items
        self.cursor = 0
        self.offset = 0

    def move(self, delta):
        self.cursor = max(0, min(len(self.items) - 1, self.cursor + delta))
        h = self.win.getmaxyx()[0] - 2
        if self.cursor < self.offset:
            self.offset = self.cursor
        elif self.cursor >= self.offset + h:
            self.offset = self.cursor - h + 1

    def current(self):
        if self.items:
            return self.items[self.cursor]
        return None

    def draw(self):
        self.win.erase()
        draw_box(self.win, self.title)
        h, w = self.win.getmaxyx()
        inner_h = h - 2
        inner_w = w - 2

        border_attr = curses.color_pair(PAIR_HEADER) | curses.A_BOLD if self.active else curses.color_pair(PAIR_BORDER)
        try:
            self.win.attrset(border_attr)
            self.win.border()
            self.win.attrset(0)
        except curses.error:
            pass

        label = f' {self.title} '
        try:
            self.win.addstr(0, max(2, (w - len(label)) // 2), label, border_attr)
        except curses.error:
            pass

        visible = self.items[self.offset: self.offset + inner_h]
        for i, item in enumerate(visible):
            idx = i + self.offset
            if isinstance(item, dict):
                text = item.get('name', str(item))
            else:
                text = str(item)
            text = text[:inner_w - 1]
            if idx == self.cursor:
                attr = curses.color_pair(PAIR_SELECTED) | curses.A_BOLD
            elif self.active:
                attr = curses.color_pair(PAIR_NORMAL)
            else:
                attr = curses.color_pair(PAIR_DIM)
            safe_addstr(self.win, i + 1, 1, f' {text:<{inner_w - 2}} ', attr)

        self.win.noutrefresh()


# ---------------------------------------------------------------------------
# Tool argument prompt
# ---------------------------------------------------------------------------

def prompt_args(stdscr, tool):
    """Simple bottom-bar prompt for tool arguments."""
    h, w = stdscr.getmaxyx()
    prompt_win = curses.newwin(5, w - 4, h // 2 - 2, 2)
    prompt_win.bkgd(' ', curses.color_pair(PAIR_NORMAL))
    draw_box(prompt_win, f'Run: {tool["name"]}')

    desc = tool.get('description', '')[:w - 8]
    safe_addstr(prompt_win, 1, 2, desc, curses.color_pair(PAIR_DIM))
    safe_addstr(prompt_win, 2, 2, 'Extra args (Enter to run, ESC to cancel): ',
                curses.color_pair(PAIR_HEADER))
    prompt_win.refresh()

    curses.echo()
    curses.curs_set(1)
    try:
        raw = prompt_win.getstr(3, 2, w - 8).decode('utf-8', errors='replace').strip()
    except Exception:
        raw = ''
    finally:
        curses.noecho()
        curses.curs_set(0)
    return raw


# ---------------------------------------------------------------------------
# Tool runner (non-blocking)
# ---------------------------------------------------------------------------

def run_tool_async(tool, extra_args, viewer, status_cb):
    """Run tool in a thread, streaming output to viewer."""
    def _run():
        path = tool['path']
        args = [sys.executable, path] + (extra_args.split() if extra_args else [])

        viewer.clear()
        viewer.append(f"Running: {' '.join(args)}\n{'─' * 60}\n")
        status_cb('running')

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors='replace',
            )
            for line in proc.stdout:
                viewer.append(line)
            proc.wait()
            viewer.append(f"\n{'─' * 60}\nExited: {proc.returncode}")
            status_cb(f'done (exit {proc.returncode})')
        except Exception as e:
            viewer.append(f"\nERROR: {e}")
            status_cb('error')

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Help overlay
# ---------------------------------------------------------------------------

HELP_TEXT = """
  LRN Admin Console — Key Bindings

  Arrow keys / j/k   Move cursor up/down
  Tab                Switch between category and tool pane
  Enter              Select category / Run selected tool
  r                  Run tool (from tool pane)
  a                  Run tool with custom arguments
  Page Up/Down       Scroll output
  Home/End           Jump to top/bottom of output
  q / ESC            Quit or go back
  ?                  This help

  The output pane shows live tool output streamed line-by-line.
  Scroll the output while a tool is running.

  Press any key to close this help.
"""


def show_help(stdscr):
    h, w = stdscr.getmaxyx()
    lines = HELP_TEXT.strip().splitlines()
    box_h = min(len(lines) + 2, h - 4)
    box_w = min(max(len(l) for l in lines) + 4, w - 4)
    win = curses.newwin(box_h, box_w, (h - box_h) // 2, (w - box_w) // 2)
    win.bkgd(' ', curses.color_pair(PAIR_NORMAL))
    draw_box(win, 'Help')
    for i, line in enumerate(lines[:box_h - 2]):
        safe_addstr(win, i + 1, 2, line, curses.color_pair(PAIR_NORMAL))
    win.refresh()
    win.getch()


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

def draw_statusbar(stdscr, msg, tool_status=''):
    h, w = stdscr.getmaxyx()
    left  = f' LRN Admin  |  {msg} '
    right = f' {tool_status} ' if tool_status else ''
    bar   = left.ljust(w - len(right) - 1) + right
    try:
        stdscr.addstr(h - 1, 0, bar[:w], curses.color_pair(PAIR_SELECTED))
    except curses.error:
        pass
    stdscr.noutrefresh()


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------

def main(stdscr):
    curses.curs_set(0)
    curses.halfdelay(2)  # Non-blocking with 200ms timeout for refresh
    init_colors()
    stdscr.bkgd(' ', curses.color_pair(PAIR_NORMAL))

    cats    = get_categories()
    by_cat  = get_tools_by_category()

    h, w = stdscr.getmaxyx()

    # Layout
    LEFT_W   = 22
    RIGHT_W  = w - LEFT_W - 1
    MENU_H   = h // 2
    OUT_H    = h - MENU_H - 1

    left_win   = curses.newwin(MENU_H, LEFT_W,     0, 0)
    right_win  = curses.newwin(MENU_H, RIGHT_W,    0, LEFT_W + 1)
    output_win = curses.newwin(OUT_H,  w,           MENU_H, 0)

    cat_pane  = MenuPane(left_win,  cats,  title='Categories')
    tool_pane = MenuPane(right_win, [],    title='Tools')
    viewer    = OutputViewer(output_win)

    cat_pane.active  = True
    tool_pane.active = False

    current_pane = 'cat'  # 'cat' or 'tool'
    tool_status  = 'idle'
    status_msg   = 'Tab=switch pane  Enter=select  r=run  a=run+args  ?=help  q=quit'

    def switch_pane():
        nonlocal current_pane
        if current_pane == 'cat':
            current_pane     = 'tool'
            cat_pane.active  = False
            tool_pane.active = True
        else:
            current_pane     = 'cat'
            cat_pane.active  = True
            tool_pane.active = False

    # Update tool pane when category changes
    def update_tools():
        cat = cat_pane.current()
        if cat:
            tools = by_cat.get(cat, [])
            tool_pane.set_items(tools)
            tool_pane.title = cat

    update_tools()

    def run_selected(with_args=False):
        nonlocal tool_status
        tool = tool_pane.current()
        if not tool or not isinstance(tool, dict):
            return
        extra = prompt_args(stdscr, tool) if with_args else ''
        tool_status = 'starting...'

        def on_status(s):
            nonlocal tool_status
            tool_status = s

        run_tool_async(tool, extra, viewer, on_status)

    while True:
        # Resize handling
        new_h, new_w = stdscr.getmaxyx()
        if (new_h, new_w) != (h, w):
            h, w = new_h, new_w
            MENU_H = h // 2
            OUT_H  = h - MENU_H - 1
            LEFT_W = min(LEFT_W, w // 3)
            RIGHT_W = w - LEFT_W - 1
            left_win.resize(MENU_H, LEFT_W)
            right_win.resize(MENU_H, RIGHT_W)
            right_win.mvwin(0, LEFT_W + 1)
            output_win.resize(OUT_H, w)
            output_win.mvwin(MENU_H, 0)

        # Draw divider
        try:
            for y in range(MENU_H):
                stdscr.addch(y, LEFT_W, curses.ACS_VLINE,
                             curses.color_pair(PAIR_BORDER))
        except curses.error:
            pass

        cat_pane.win  = left_win
        tool_pane.win = right_win
        viewer.win    = output_win

        cat_pane.draw()
        tool_pane.draw()
        viewer.draw('Output  (PgUp/PgDn to scroll)')
        draw_statusbar(stdscr, status_msg, tool_status)
        curses.doupdate()

        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        if key == -1:
            continue  # timeout — just refresh

        if key in (ord('q'), ord('Q')):
            if current_pane == 'tool':
                switch_pane()
            else:
                break

        elif key == 27:  # ESC
            if current_pane == 'tool':
                switch_pane()
            else:
                break

        elif key == ord('?'):
            show_help(stdscr)

        elif key == 9:  # Tab
            switch_pane()

        elif key in (curses.KEY_UP, ord('k')):
            if current_pane == 'cat':
                cat_pane.move(-1)
                update_tools()
            else:
                tool_pane.move(-1)

        elif key in (curses.KEY_DOWN, ord('j')):
            if current_pane == 'cat':
                cat_pane.move(1)
                update_tools()
            else:
                tool_pane.move(1)

        elif key == curses.KEY_PPAGE:
            viewer.scroll(-10)

        elif key == curses.KEY_NPAGE:
            viewer.scroll(10)

        elif key == curses.KEY_HOME:
            viewer.scroll(-9999)

        elif key == curses.KEY_END:
            viewer.scroll(9999)

        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            if current_pane == 'cat':
                switch_pane()
            else:
                run_selected(with_args=False)

        elif key == ord('r'):
            if current_pane == 'tool':
                run_selected(with_args=False)

        elif key == ord('a'):
            if current_pane == 'tool':
                run_selected(with_args=True)

        elif key == curses.KEY_RIGHT:
            if current_pane == 'cat':
                switch_pane()

        elif key == curses.KEY_LEFT:
            if current_pane == 'tool':
                switch_pane()


def cli_main():
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    print("\nGoodbye.")


if __name__ == '__main__':
    cli_main()
