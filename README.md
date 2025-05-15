# DJIVideoExtrator
Turn Avata Video &amp; Subtitle Into Geotagged Photos

## Usage

```bash
dji_geotagger.py -i /path/to/videos -o /path/to/output [-q QUALITY] [-s START] [-e END] [-f FPS_SAMPLE]
```

### Options

| Option               | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| `-i`, `--input-dir`  | Directory with video & SRT files (default: current directory)               |
| `-o`, `--output-dir` | Directory for output frames (default: current directory)                    |
| `-q`, `--quality`    | JPEG quality (1 = best, 31 = worst; default: 2)                             |
| `-s`, `--start`      | Start time in seconds (float; default: beginning of video)                  |
| `-e`, `--end`        | End time in seconds (float; default: end of video)                          |
| `-f`, `--fps-sample` | Frames to extract per second (int; default: all frames)                     |

## Dependencies

- Python 3.6+
- [ffmpeg](https://ffmpeg.org/) (must be in your system `PATH`)
- [ffprobe](https://ffmpeg.org/ffprobe.html) (included with ffmpeg, also in `PATH`)
- [exiftool](https://exiftool.org/) (must be in your system `PATH`)
- [pysrt](https://pypi.org/project/pysrt/) (`pip install pysrt`)



I can't believe I am asking gpt for writing this...
sorry!
