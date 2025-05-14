#!/usr/bin/env python3
"""
DJI Frame Extractor & Geotagger (JPEG)

Extracts frames from DJI drone videos at high-quality JPEG and geotags each frame with full telemetry from DJI-generated SRT files.

Usage:
    dji_geotagger.py --input-dir /path/to/videos --output-dir /path/to/output

If not specified, both input and output default to the current directory.

Dependencies:
    - Python 3.6+
    - ffmpeg (in PATH)
    - ffprobe (in PATH)
    - exiftool (in PATH)
    - pysrt (pip install pysrt)
"""
import argparse
import os
import re
import subprocess
import shutil
import sys
from datetime import datetime, timedelta

try:
    import pysrt
except ImportError:
    print("Missing dependency: pysrt. Install with `pip install pysrt`.")
    sys.exit(1)

# Regex patterns for parsing SRT telemetry blocks
timecode_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
bracket_re = re.compile(r"\[([^:\]]+):\s*([^\]]+)\]")

# Required external tools
TOOLS = ('ffmpeg', 'ffprobe', 'exiftool')

def check_dependencies():
    for t in TOOLS:
        if not shutil.which(t):
            print(f"Error: '{t}' is not installed or not in your PATH.")
            sys.exit(1)

def get_video_fps(video_path):
    cmd = [
        'ffprobe', '-v', '0', '-of', 'csv=p=0', '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate', video_path
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    if '/' in out:
        num, den = map(int, out.split('/'))
    else:
        num, den = int(out), 1
    return num / den

def extract_frames(video_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, 'frame_%06d.jpg')
    # High-quality JPEG extraction (~original quality)
    subprocess.run([
        'ffmpeg', '-i', video_path,
        '-vsync', '0', '-qscale:v', '2', pattern
    ], check=True)

'''
try 3 maybe?
Quality Value (-q:v)    Quality Level   Notes
1                       Best possible   May require also -qmin 1.
2–5                     Very high       Commonly recommended sweet spot.
6–10                    High            Good balance for web thumbnails.
11–20                   Medium          Noticeable compression artifacts.
21–31                   Low             Severe artifacts, small file size.
'''

def parse_srt_block(text):
    data = {}
    # Extract timestamp
    m = timecode_re.search(text)
    if m:
        ts = m.group(1)
        dt = datetime.strptime(ts.split('.')[0], '%Y-%m-%d %H:%M:%S')
        data['DateTimeOriginal'] = dt.strftime('%Y:%m:%d %H:%M:%S')
    # Extract key/value telemetry
    for key, val in bracket_re.findall(text):
        data[key.strip()] = val.strip()
    return data


def geotag_frames(frames_dir, srt_path, fps, start_dt):
    subs = pysrt.open(srt_path)
    for sub in subs:
        meta = parse_srt_block(sub.text)
        # Compute frame index from timestamp
        td = timedelta(
            hours=sub.start.hours,
            minutes=sub.start.minutes,
            seconds=sub.start.seconds,
            milliseconds=sub.start.milliseconds
        )
        idx = int(td.total_seconds() * fps) + 1
        frame_file = os.path.join(frames_dir, f'frame_{idx:06d}.jpg')
        if not os.path.exists(frame_file):
            continue
        # Build exiftool command
        cmd = ['exiftool', '-m', '-overwrite_original']
        # GPS fields
        lat = meta.get('latitude')
        lon = meta.get('longitude')
        alt = meta.get('abs_alt') or meta.get('rel_alt')
        if lat and lon:
            cmd += [f'-GPSLatitude={lat}', f'-GPSLongitude={lon}']
        if alt:
            cmd += [f'-GPSAltitude={alt}']
        # Map other telemetry to EXIF tags
        tagmap = {
            'iso': '-ISO',
            'shutter': '-ShutterSpeedValue',
            'fnum': '-ApertureValue',
            'ev': '-ExposureCompensation',
            'ct': '-ColorTemperature',
            'color_md': '-ColorMode',
            'focal_len': '-FocalLength'
        }
        for key, exif_tag in tagmap.items():
            if key in meta:
                cmd.append(f"{exif_tag}={meta[key]}")
        # DateTimeOriginal
        if 'DateTimeOriginal' in meta:
            cmd.append(f"-DateTimeOriginal={meta['DateTimeOriginal']}")
        # Remaining telemetry in UserComment
        extras = {k: v for k, v in meta.items() if k not in tagmap and k not in ('DateTimeOriginal','latitude','longitude','abs_alt','rel_alt')}
        if extras:
            comment = ';'.join(f'{k}={v}' for k, v in extras.items())
            cmd.append(f"-UserComment={comment}")
        # Target file
        cmd.append(frame_file)
        subprocess.run(cmd, check=True)


def get_start_datetime(video_path):
    # Use file modification time as proxy for recording start
    ts = os.path.getmtime(video_path)
    return datetime.fromtimestamp(ts)


def main():
    parser = argparse.ArgumentParser(description='Extract JPEG frames and full geotag from DJI video')
    parser.add_argument('--input-dir', default='.', help='Directory with video & SRT files')
    parser.add_argument('--output-dir', default='.', help='Directory for output frames')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    # Resolve paths to absolute
    in_root = os.path.abspath(os.path.expanduser(args.input_dir))
    out_root = os.path.abspath(os.path.expanduser(args.output_dir))

    check_dependencies()

    for fname in os.listdir(in_root):
        if not fname.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            continue
        base, _ = os.path.splitext(fname)
        video_path = os.path.join(in_root, fname)
        srt_path = os.path.join(in_root, base + '.srt')
        if not os.path.exists(srt_path):
            print(f"[WARN] Missing SRT for {fname}, skipping.")
            continue

        fps = get_video_fps(video_path)
        start_dt = get_start_datetime(video_path)
        frames_dir = os.path.join(out_root, base)

        print(f"Processing {fname} -> {frames_dir}")
        extract_frames(video_path, frames_dir)
        geotag_frames(frames_dir, srt_path, fps, start_dt)
        print(f"Completed: {base}")

if __name__ == '__main__':
    main()
