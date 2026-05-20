#!/bin/python
import subprocess
import re
import time
import json
import sys
import signal
import os
from urllib.parse import quote

OFFSET = -0.3

def get_track():
    try:
        result = subprocess.run(["playerctl", "metadata", "-f", "{{artist}}|{{title}}"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('|')
    except:
        pass
    return None, None

def get_lyrics(artist, title):
    url = f"https://lrclib.net/api/get?track_name={quote(title)}&artist_name={quote(artist)}"
    try:
        result = subprocess.run(["curl", "-s", "--max-time", "2", url], capture_output=True, text=True)
        data = json.loads(result.stdout)
        return data.get('syncedLyrics')
    except:
        return None

def parse_lrc(text):
    lines = []
    if not text: return lines
    for line in text.split('\n'):
        match = re.match(r'\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]\s*(.*)', line)
        if match:
            minutes, seconds = int(match.group(1)), int(match.group(2))
            millis = int(match.group(3) or 0)
            if len(match.group(3) or "") < 3: millis *= 10
            lines.append({'time': minutes * 60 + seconds + millis / 1000 + OFFSET, 'text': match.group(4).strip()})
    return sorted(lines, key=lambda x: x['time'])

def get_pos():
    try:
        res = subprocess.run(["playerctl", "position"], capture_output=True, text=True)
        return float(res.stdout.strip())
    except:
        return 0.0

def cleanup(sig, frame):
    sys.stdout.write("\033[2J\033[H\033[?25h")
    sys.stdout.flush()
    os._exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

last_track = ""
lines = []
last_idx = -2
last_pos = -1.0

sys.stdout.write("\033[?25l")
sys.stdout.flush()

while True:
    artist, title = get_track()
    track = f"{artist}|{title}"

    if track != last_track:
        last_track = track
        last_idx = -2
        last_pos = -1.0
        lines = parse_lrc(get_lyrics(artist, title)) if artist else []
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    if lines:
        pos = get_pos()
        is_seeked = abs(pos - last_pos) > 1.0

        idx = -1
        for i, line in enumerate(lines):
            if line['time'] <= pos:
                idx = i

        if idx != last_idx or is_seeked:
            try:
                rows, cols = os.popen('stty size', 'r').read().split()
                rows, cols = int(rows), int(cols)
            except:
                rows, cols = 24, 80

            center_y = rows // 2

            def print_line(y, text, color="\033[0m"):
                x = max(0, (cols - len(text)) // 2)
                sys.stdout.write(f"\033[{y};1H\033[K\033[{y};{x+1}H{color}{text}\033[0m")

            print_line(center_y, lines[idx-1]['text'] if idx > 0 else "", "\033[90m")
            print_line(center_y + 1, lines[idx]['text'] if idx >= 0 else "", "\033[1;97m")

            sys.stdout.flush()
            last_idx = idx
            last_pos = pos

    time.sleep(0.1)
