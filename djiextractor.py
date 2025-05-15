#!/usr/bin/env python3
"""
DJI Frame Extractor & Geotagger (JPEG)

Extracts frames from DJI drone videos at high-quality JPEG, with optional trimming,
sampling, and geotagging using DJI SRT telemetry.

Usage:
    dji_geotagger.py -i /path/to/videos -o /path/to/output [-q QUALITY] [-s START] [-e END] [-f FPS_SAMPLE]

Options:
    -i, --input-dir      Directory with video & SRT files (default: current dir)
    -o, --output-dir     Directory for output frames (default: current dir)
    -q, --quality        JPEG quality (1=best, 31=worst; default: 2)
    -s, --start          Start time in seconds (float; default=beginning)
    -e, --end            End time in seconds (float; default=end)
    -f, --fps-sample     Frames to extract per second (int; default=all frames)

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
bracket_re  = re.compile(r"\[([^:\]]+):\s*([^\]]+)\]")

# External tools required
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

def extract_frames(video_path, out_dir, quality, start, end, fps_sample):
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, 'frame_%06d.jpg')
    cmd = [
    'ffmpeg',
    # <-- Log only errors, update progress every 5 seconds
    '-loglevel', 'error',
    '-stats_period', '5',
    # <-- Preserve original frame timing
    '-fps_mode', 'passthrough',
    ]
    
    if start is not None:
        cmd += ['-ss', str(start)]
    if end is not None:
        cmd += ['-to', str(end)]
    cmd += ['-i', video_path]
    if fps_sample is not None:
        cmd += ['-vf', f'fps={fps_sample}']
    cmd += [
        '-qscale:v', str(quality),
        '-qmin', str(quality),
        pattern
    ]
    subprocess.run(cmd, check=True)

def parse_srt_block(text):
    data = {}
    m = timecode_re.search(text)
    if m:
        ts = m.group(1)
        dt = datetime.strptime(ts.split('.')[0], '%Y-%m-%d %H:%M:%S')
        data['DateTimeOriginal'] = dt.strftime('%Y:%m:%d %H:%M:%S')
    for key, val in bracket_re.findall(text):
        data[key.strip()] = val.strip()
    return data

def geotag_frames(frames_dir, srt_path, fps, start_dt):
    subs = pysrt.open(srt_path)
    for sub in subs:
        meta = parse_srt_block(sub.text)
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
        cmd = [
            'exiftool',
            '-TagsFromFile', '@', '-all:all',    # preserve absolutely every tag
            '-m',                                # ignore minor warnings
                # Ignore minor warnings (already added as -m)
                # Write as raw values (no PrintConv) by adding -n when you know the tag expects a numeric value
            '-overwrite_original',
        ]
        lat = meta.get('latitude')
        lon = meta.get('longitude')
        alt = meta.get('abs_alt') or meta.get('rel_alt')
        if lat and lon:
            cmd += [f'-GPSLatitude={lat}', f'-GPSLongitude={lon}']
        if alt:
            cmd += [f'-GPSAltitude={alt}']
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
        if 'DateTimeOriginal' in meta:
            cmd.append(f"-DateTimeOriginal={meta['DateTimeOriginal']}")
        extras = {
            k: v for k, v in meta.items()
            if k not in tagmap and k not in ('DateTimeOriginal','latitude','longitude','abs_alt','rel_alt')
        }
        if extras:
            comment = ';'.join(f'{k}={v}' for k, v in extras.items())
            cmd.append(f"-UserComment={comment}")
        cmd.append(frame_file)
        subprocess.run(cmd, check=True)

def get_start_datetime(video_path):
    ts = os.path.getmtime(video_path)
    return datetime.fromtimestamp(ts)

def main():
    parser = argparse.ArgumentParser(description='Extract & geotag frames from DJI video')
    parser.add_argument('-i','--input-dir',   default='.', help='Directory with video & SRT files')
    parser.add_argument('-o','--output-dir',  default='.', help='Directory for output frames')
    parser.add_argument('-q','--quality',     type=int,   default=2, choices=range(1,32),
                        help='JPEG quality (1=best,31=worst)')
    parser.add_argument('-s','--start',       type=float, default=None,
                        help='Start time in seconds (default=beginning)')
    parser.add_argument('-e','--end',         type=float, default=None,
                        help='End time in seconds (default=end)')
    parser.add_argument('-f','--fps-sample',  type=int,   default=None,
                        help='Frames to extract per second (default=all)')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    # Edge-case checks
    if args.start is not None and args.start < 0:
        sys.exit("Error: --start must be ≥ 0")
    if args.end is not None and args.end <= 0:
        sys.exit("Error: --end must be > 0")
    if args.start is not None and args.end is not None and args.end <= args.start:
        sys.exit("Error: --end must be > --start")
    if args.fps_sample is not None and args.fps_sample <= 0:
        sys.exit("Error: --fps-sample must be > 0")

    in_root  = os.path.abspath(os.path.expanduser(args.input_dir))
    out_root = os.path.abspath(os.path.expanduser(args.output_dir))
    check_dependencies()

    for fname in os.listdir(in_root):
        if fname.lower().endswith(('.mp4','.mov','.avi','.mkv')):
            base      = os.path.splitext(fname)[0]
            video     = os.path.join(in_root, fname)
            srt_file  = os.path.join(in_root, f"{base}.srt")
            if not os.path.exists(srt_file):
                print(f"[WARN] Missing SRT for {fname}, skipping.")
                continue
            fps      = get_video_fps(video)
            start_dt = get_start_datetime(video)
            out_dir  = os.path.join(out_root, base)

            print(f"Processing {fname} -> {out_dir}")
            extract_frames(video, out_dir,
                           quality    = args.quality,
                           start      = args.start,
                           end        = args.end,
                           fps_sample = args.fps_sample)
            geotag_frames(out_dir, srt_file, fps, start_dt)
            print(f"Completed: {base}")

if __name__ == '__main__':
    main()
