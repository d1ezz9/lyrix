#!/usr/bin/env python3
import subprocess
import re
import time
import json
import sys
import signal
import os
import urllib.request
import urllib.parse
import concurrent.futures

LYRICS_CACHE = {}

OFFSET = -0.3

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
RESET = "\033[0m"
COLOR_GRAY = "\033[90m"
COLOR_BRIGHT_WHITE = "\033[1;97m"

TIMESTAMP_RE = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]')

def get_track():
    try:
        result = subprocess.run(["playerctl", "metadata", "-f", "{{artist}}|{{title}}"],
                                capture_output=True, text=True, timeout=1)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split('|', 1)
            artist = parts[0].strip() if parts else None
            title = parts[1].strip() if len(parts) > 1 else None
            if artist and title:
                return artist, title
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        pass
    return None, None

def get_lyrics(artist, title):
    key = f"{artist.lower()}|{title.lower()}"
    if key in LYRICS_CACHE:
        return LYRICS_CACHE[key]
    
    clean_artist = artist.strip()
    clean_title = title.strip()
    search_url = f"https://lrclib.net/api/search?track_name={urllib.parse.quote(clean_title)}&artist_name={urllib.parse.quote(clean_artist)}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if isinstance(data, list) and len(data) > 0:
                        for item in data:
                            if item.get("syncedLyrics") or item.get("plainLyrics"):
                                res = (item.get("syncedLyrics") or item.get("plainLyrics")).strip()
                                LYRICS_CACHE[key] = res
                                return res
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            return None
    return None

def parse_lrc(text):
    lines = []
    if not text:
        return lines

    has_timestamps = False
    raw_lines = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        matches = TIMESTAMP_RE.findall(line)
        if matches:
            has_timestamps = True
            lyric_text = re.sub(r'^(?:\[[^\]]+\])+', '', line).strip()
            for m in matches:
                minutes = int(m[0])
                seconds = int(m[1])
                millis_str = m[2] if m[2] else "0"
                if len(millis_str) == 1:
                    millis = int(millis_str) * 100
                elif len(millis_str) == 2:
                    millis = int(millis_str) * 10
                else:
                    millis = int(millis_str)
                time_seconds = minutes * 60 + seconds + millis / 1000.0 + OFFSET
                raw_lines.append({'time': time_seconds, 'text': lyric_text})
        else:
            raw_lines.append({'time': None, 'text': line})

    if not has_timestamps:
        return [{'time': None, 'text': item['text']} for item in raw_lines]

    synced = [l for l in raw_lines if l.get('time') is not None]
    synced = sorted(synced, key=lambda x: x['time'])
    return synced

def get_pos():
    try:
        res = subprocess.run(["playerctl", "position"], capture_output=True, text=True, timeout=1)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return 0.0

def get_terminal_size():
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except (AttributeError, OSError):
        return 24, 80

def wrap_text(text, cols):
    if not text:
        return [""]
    if cols <= 0:
        return [text]
    if len(text) <= cols:
        return [text]
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if not current_line:
            if len(word) > cols:
                start = 0
                while start < len(word):
                    part = word[start:start + cols]
                    lines.append(part)
                    start += cols
            else:
                current_line = word
        elif len(current_line) + 1 + len(word) <= cols:
            current_line += " " + word
        else:
            lines.append(current_line)
            if len(word) > cols:
                start = 0
                while start < len(word):
                    part = word[start:start + cols]
                    lines.append(part)
                    start += cols
                current_line = ""
            else:
                current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else [""]

def draw_synced(center_y, prev_text, curr_text, next_text, cols):
    sys.stdout.write(CLEAR_SCREEN)
    prev_display = (wrap_text(prev_text, cols)[-1] if prev_text else "")
    curr_display = (wrap_text(curr_text, cols)[0] if curr_text else "")
    next_display = (wrap_text(next_text, cols)[0] if next_text else "")
    prev_x = max(0, (cols - len(prev_display)) // 2)
    curr_x = max(0, (cols - len(curr_display)) // 2)
    next_x = max(0, (cols - len(next_display)) // 2)
    try:
        sys.stdout.write(f"\033[{center_y - 1};{prev_x + 1}H{COLOR_GRAY}{prev_display}{RESET}")
        sys.stdout.write(f"\033[{center_y};{curr_x + 1}H{COLOR_BRIGHT_WHITE}{curr_display}{RESET}")
        sys.stdout.write(f"\033[{center_y + 1};{next_x + 1}H{COLOR_GRAY}{next_display}{RESET}")
        sys.stdout.flush()
    except Exception:
        pass

def draw_plain(lines, scroll_offset, rows, cols):
    sys.stdout.write(CLEAR_SCREEN)
    visible_lines = rows - 2
    start = scroll_offset
    end = min(start + visible_lines, len(lines))
    display_start_row = 2
    for i, line_text in enumerate(lines[start:end]):
        row = display_start_row + i
        wrapped = wrap_text(line_text, cols)
        text = wrapped[0] if wrapped else ""
        x = max(0, (cols - len(text)) // 2)
        sys.stdout.write(f"\033[{row};{x + 1}H{COLOR_BRIGHT_WHITE}{text}{RESET}")
    hint = "[ scroll: arrow up/down or j/k ]"
    hx = max(0, (cols - len(hint)) // 2)
    sys.stdout.write(f"\033[{rows};{hx + 1}H{COLOR_GRAY}{hint}{RESET}")
    sys.stdout.flush()

def set_terminal_raw(enabled):
    import termios, tty
    global _old_term_settings
    fd = sys.stdin.fileno()
    if enabled:
        _old_term_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    else:
        termios.tcsetattr(fd, termios.TCSADRAIN, _old_term_settings)

def read_key_nonblocking():
    import select
    if select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        ch3 = sys.stdin.read(1)
                        return 'ESC_' + ch3
        return ch
    return None

def cleanup(sig=None, frame=None):
    try:
        set_terminal_raw(False)
    except Exception:
        pass
    sys.stdout.write(CLEAR_SCREEN + SHOW_CURSOR)
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def check_dependencies():
    for cmd in ["playerctl"]:
        if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
            print(f"Error: Required dependency '{cmd}' not found.")
            sys.exit(1)

check_dependencies()

_old_term_settings = None

last_track = ""
lines = []
last_idx = -2
last_pos = -1.0
is_plain_mode = False
plain_scroll = 0

try:
    set_terminal_raw(True)
except Exception:
    pass

sys.stdout.write(HIDE_CURSOR)
sys.stdout.flush()

while True:
    try:
        artist, title = get_track()
        track = f"{artist}|{title}" if artist and title else ""

        if track != last_track:
            last_track = track
            last_idx = -2
            last_pos = -1.0
            plain_scroll = 0
            if artist and title:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(get_lyrics, artist, title)
                    raw_lines = parse_lrc(future.result())
            else:
                raw_lines = []

            if raw_lines and raw_lines[0]['time'] is None:
                is_plain_mode = True
                lines = [l['text'] for l in raw_lines]
            else:
                is_plain_mode = False
                lines = raw_lines

            rows, cols = get_terminal_size()
            center_y = rows // 2
            sys.stdout.write(CLEAR_SCREEN)
            if not lines:
                msg = "No lyrics found"
                x = max(0, (cols - len(msg)) // 2)
                sys.stdout.write(f"\033[{center_y};{x + 1}H{COLOR_GRAY}{msg}{RESET}")
                sys.stdout.flush()
            elif is_plain_mode:
                draw_plain(lines, plain_scroll, rows, cols)

        key = read_key_nonblocking()
        if key in ('q', 'Q'):
            cleanup()

        if is_plain_mode and lines:
            rows, cols = get_terminal_size()
            visible_lines = rows - 2
            max_scroll = max(0, len(lines) - visible_lines)
            scrolled = False
            if key in ('ESC_A', 'k', 'K'):
                plain_scroll = max(0, plain_scroll - 1)
                scrolled = True
            elif key in ('ESC_B', 'j', 'J'):
                plain_scroll = min(max_scroll, plain_scroll + 1)
                scrolled = True
            if scrolled:
                draw_plain(lines, plain_scroll, rows, cols)

        if not is_plain_mode and lines:
            pos = get_pos()
            is_seeked = abs(pos - last_pos) > 2.0 and last_pos >= 0
            idx = -1
            for i, line in enumerate(lines):
                if line['time'] <= pos:
                    idx = i
                else:
                    break

            if idx != last_idx or is_seeked:
                rows, cols = get_terminal_size()
                center_y = rows // 2
                prev_text = lines[idx - 1]['text'] if idx > 0 else ""
                curr_text = lines[idx]['text'] if 0 <= idx < len(lines) else ""
                next_text = lines[idx + 1]['text'] if idx + 1 < len(lines) else ""
                draw_synced(center_y, prev_text, curr_text, next_text, cols)
                last_idx = idx
                last_pos = pos

        time.sleep(0.1)
    except KeyboardInterrupt:
        break
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        time.sleep(0.5)

cleanup()
