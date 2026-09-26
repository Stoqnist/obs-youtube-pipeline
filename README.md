01 — Record (OBS, one-time, UI path)
Settings → Output → Recording:

Format: MKV (crash-safe)
Remux Recording: checked (gives you a fallback MP4 even if the pipeline never runs)
Video Encoder: x264 (CPU) or NVENC H.264; Quality (CQP): 0 — verify at that panel for your OBS version, it sits under the FFmpeg output settings
Track 1: primary mic (only track enabled, so 0:a:0 is always your mic)
Canvas: 1920x1080 (3840x2160 only if both cams are 4K and GPU has headroom)

# Setup + usage
## Prerequisites (one per OS):
#### macOS
`brew install ffmpeg`
#### Linux (Debian/Ubuntu)
`sudo apt install ffmpeg`
#### Windows
`winget install Gyan.FFmpeg`

## Optional — local transcription (whisper.cpp + large-v3):
```bash
brew install whisper-cpp        # macOS — provides whisper-cli
# Linux: build whisper.cpp (cmake) or: sudo apt install whisper-cpp (Ubuntu 24.04+)
mkdir -p models && curl -L -o models/ggml-large-v3.bin \
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin
```

## Manual run (any time, one recording):
```bash
python3 process_recording.py "2026-02-03 14.00.00.mkv" --project interview --transcribe
# outputs: 20260203_interview_1080p.mp4, 20260203_interview_16k.wav, 20260203_interview.srt/.txt
```

## Batch (a folder of recordings from one project):
```bash
python3 process_recording.py --batch ./OBS_recordings --project daily --transcribe
```

## Fully automatic (every recording, triggered by OBS):
```bash
pip install obsws-python
export OBS_WEBSOCKET_KEY='...OBS websocket password...'   # set in your shell profile, not in a script
export OBS_RECORDINGS="$HOME/Movies"
python3 watch_recordings.py     # leave running; it processes each recording the moment you stop it
```

Trigger options (one-line tradeoffs): obs-websocket RecordOutputStopped (shown above — most robust, needs the plugin, recommended for production) · OBS Python script with on_exit hook (zero dependencies, dies with OBS — quick setups) · file watcher (fswatch on macOS / PowerShell FileSystemWatcher on Windows — fully decoupled from OBS).

## Verification (stage 06)
The script already asserts all of this and exits non-zero on mismatch. Manual one-liners if you want to double-check:
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,width,height -of csv=p=0 20260203_interview_1080p.mp4
# expect: h264,High,1920,1080
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of csv=p=0 20260203_interview_1080p.mp4
# expect: aac,48000,2
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels -of csv=p=0 20260203_interview_16k.wav
# expect: pcm_s16le,16000,1
```
Dry run before trusting it: record 30 s → python3 process_recording.py <that.mkv> --project dryrun --transcribe → confirm the _1080p.mp4, _16k.wav, and .srt all exist and the verify block prints all [OK].

One note: OBS's remux-after-recording MP4 keeps the original filename, so it never collides with the pipeline's YYYYMMDD_project_1080p.mp4 output. Tell me your OS (and whether GPU is NVIDIA) and I'll tighten the install lines and confirm the CQP panel location for your OBS version.










