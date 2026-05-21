#!/usr/bin/env python3
import subprocess
import re
import time
import json
import sys
import signal
import os
from urllib.parse import quote

OFFSET = -0.3

LRC_PATTERN = re.compile(r'\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]\s*(.*)')

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
RESET = "\033[0m"
COLOR_GRAY = "\033[90m"
COLOR_BRIGHT_WHITE = "\033[1;97m"

def get_track():
    try:
        result = subprocess.run(["playerctl", "metadata", "-f", "{{artist}}|{{title}}"], capture_output=True, text=True, timeout=1)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split('|')
            return parts[0], parts[1]
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        pass
    return None, None

def get_lyrics(artist, title):
    url = f"https://lrclib.net/api/get?track_name={quote(title)}&artist_name={quote(artist)}"
    try:
        result = subprocess.run(["curl", "-s", "--max-time", "2", url], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('syncedLyrics')
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None

def parse_lrc(text):
    lines = []
    if not text:
        return lines
    for line in text.split('\n'):
        match = LRC_PATTERN.match(line)
        if match:
            minutes, seconds = int(match.group(1)), int(match.group(2))
            millis_str = match.group(3) or "0"
            millis = int(millis_str)
            if len(millis_str) < 3:
                millis *= 10
            time_seconds = minutes * 60 + seconds + millis / 1000 + OFFSET
            lines.append({'time': time_seconds, 'text': match.group(4).strip()})
    return sorted(lines, key=lambda x: x['time'])

def get_pos():
    try:
        res = subprocess.run(["playerctl", "position"], capture_output=True, text=True, timeout=1)
        return float(res.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 0.0

def get_terminal_size():
    try:
        rows, cols = os.popen('stty size', 'r').read().split()
        return int(rows), int(cols)
    except (ValueError, OSError):
        return 24, 80

def wrap_text(text, cols):
    if len(text) <= cols:
        return [text]
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= cols:
            current_line += (word if not current_line else " " + word)
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else [text[:cols]]

def draw_lyrics(center_y, prev_text, curr_text, next_text):
    rows, cols = get_terminal_size()
    sys.stdout.write(CLEAR_SCREEN)
    prev_lines = wrap_text(prev_text, cols) if prev_text else [""]
    curr_lines = wrap_text(curr_text, cols) if curr_text else [""]
    next_lines = wrap_text(next_text, cols) if next_text else [""]
    prev_display = prev_lines[-1] if prev_lines else ""
    curr_display = curr_lines[0] if curr_lines else ""
    next_display = next_lines[0] if next_lines else ""
    prev_x = max(0, (cols - len(prev_display)) // 2)
    curr_x = max(0, (cols - len(curr_display)) // 2)
    next_x = max(0, (cols - len(next_display)) // 2)
    sys.stdout.write(f"\033[{center_y - 1};{prev_x + 1}H{COLOR_GRAY}{prev_display}{RESET}")
    sys.stdout.write(f"\033[{center_y};{curr_x + 1}H{COLOR_BRIGHT_WHITE}{curr_display}{RESET}")
    sys.stdout.write(f"\033[{center_y + 1};{next_x + 1}H{COLOR_GRAY}{next_display}{RESET}")
    sys.stdout.flush()

def cleanup(sig, frame):
    sys.stdout.write(CLEAR_SCREEN + SHOW_CURSOR)
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

last_track = ""
lines = []
last_idx = -2
last_pos = -1.0

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
            lines = parse_lrc(get_lyrics(artist, title)) if artist and title else []
            rows, cols = get_terminal_size()
            center_y = rows // 2
            sys.stdout.write(CLEAR_SCREEN)
            if not lines:
                msg = "No lyrics found"
                x = max(0, (cols - len(msg)) // 2)
                sys.stdout.write(f"\033[{center_y};{x + 1}H{msg}")
            sys.stdout.flush()

        if lines:
            pos = get_pos()
            is_seeked = abs(pos - last_pos) > 1.0
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
                curr_text = lines[idx]['text'] if idx >= 0 else ""
                next_text = lines[idx + 1]['text'] if idx + 1 < len(lines) else ""
                draw_lyrics(center_y, prev_text, curr_text, next_text)
                last_idx = idx
                last_pos = pos

        time.sleep(0.1)
    except KeyboardInterrupt:
        break
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        time.sleep(0.5)
