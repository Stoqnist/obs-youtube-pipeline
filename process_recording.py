#!/usr/bin/env python3
"""process_recording.py — OBS recording -> YouTube-ready MP4 + 16 kHz WAV (+ optional Whisper SRT/TXT).

Stdlib only; requires ffmpeg + ffprobe in PATH.
Stages: 02 export  03 extract 16k audio  04 verify

Usage:
  python3 process_recording.py "2026-02-03 14.00.00.mkv" --project interview
  python3 process_recording.py --batch ./OBS_recordings --project interview
"""
import argparse, datetime, json, re, shutil, subprocess, sys
from pathlib import Path


def run(cmd, cwd=None):
    print("\n$ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                          "-show_streams", str(path)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s.get("codec_type") == "video")
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    return v, a


def process(src: Path, args):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("error: ffmpeg/ffprobe not in PATH — install ffmpeg first.")
    if not src.exists():
        sys.exit(f"error: input not found: {src}")

    # naming: YYYYMMDD_project (date taken from file mtime = recording time)
    date = datetime.datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
    project = re.sub(r"[^A-Za-z0-9_-]+", "_", args.project).strip("_") if args.project else "recording"
    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else src.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{project}"
    mp4 = outdir / f"{stem}_1080p.mp4"
    wav = outdir / f"{stem}_16k.wav"

    # probe source
    v, a = probe(src)
    print(f"source: {src.name} | video {v.get('codec_name')} {v.get('width')}x{v.get('height')}"
          f" | audio {(a or {}).get('codec_name', '-')} {(a or {}).get('sample_rate', '-')} Hz")
    if a is None:
        sys.exit("error: no audio stream in source.")

    v_ok = (v.get("codec_name") == "h264" and int(v.get("width", 0)) == 1920
            and int(v.get("height", 0)) == 1080)
    a_ok = (a.get("codec_name") == "aac" and a.get("sample_rate") == "48000")

    # 02 YouTube export — 3 branches: full copy / copy video + encode audio / full re-encode
    if not args.force_reencode and v_ok and a_ok:
        print("02 -> stream-copy remux (source already meets YouTube spec)")
        run(["ffmpeg", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0",
             "-c", "copy", "-movflags", "+faststart", mp4])
    elif not args.force_reencode and v_ok:
        print("02 -> copy H.264 video, re-encode audio to AAC 320k (typical OBS MKV has FLAC)")
        run(["ffmpeg", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
             "-movflags", "+faststart", mp4])
    else:
        print("02 -> re-encode H.264 CRF18 + AAC 320k")
        run(["ffmpeg", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0",
             "-c:v", "libx264", "-preset", "slow", "-crf", "18",
             "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-vf", "scale=1920:1080",          # assumes 16:9 source (OBS canvas 1080p/4K)
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
             "-movflags", "+faststart", mp4])

    # 03 16 kHz mono PCM WAV for Whisper (lossless, exact sample rate)
    print("03 -> extract transcription audio")
    run(["ffmpeg", "-y", "-i", mp4, "-vn", "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1", wav])

    # 04 verify
    vv, aa = probe(mp4)
    checks = [("video codec", vv.get("codec_name"), "h264"),
              ("resolution", f'{vv.get("width")}x{vv.get("height")}', "1920x1080"),
              ("audio codec", aa.get("codec_name"), "aac"),
              ("sample rate", aa.get("sample_rate"), "48000")]
    ok = True
    print("05 -> verify:")
    for name, got, want in checks:
        ok &= (got == want)
        print(f"   [{'OK' if got == want else 'MISMATCH'}] {name}: {got} (expected {want})")
    print(f"   [OK] wav: {wav.name} ({wav.stat().st_size // 1024} KiB)")
    print(f"\ndone: {mp4}")

def main():
    ap = argparse.ArgumentParser(description="OBS recording -> YouTube MP4 + 16 kHz WAV (+ optional Whisper SRT/TXT)")
    ap.add_argument("input", nargs="?", help="input .mkv/.mp4 from OBS")
    ap.add_argument("--batch", metavar="DIR", help="process every .mkv in DIR (one project per folder)")
    ap.add_argument("--project", default=None, help="project name in output filenames (default: 'recording')")
    ap.add_argument("--outdir", default=None, help="output directory (default: next to the input)")
    ap.add_argument("--whisper", default=None, help="path to whisper-cli (or main) if not in PATH")
    ap.add_argument("--force-reencode", action="store_true", help="never use the stream-copy shortcut")
    args = ap.parse_args()

    if not args.input and not args.batch:
        ap.error("provide an input file or --batch DIR")
    if args.batch:
        files = list(Path(args.batch).expanduser().resolve().glob("*.mkv"))
    else:
        files = [Path(args.input).expanduser().resolve()]
    files = sorted(p for p in files if p.exists())
    if not files:
        sys.exit("error: no input .mkv files found")

    failures = 0
    for f in files:
        print(f"\n=== {f} " + "=" * 40)
        try:
            process(f, args)
        except subprocess.CalledProcessError as e:
            failures += 1
            print(f"FAILED: {f} (command exited {e.returncode})", file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()