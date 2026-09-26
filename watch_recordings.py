#!/usr/bin/env python3
"""watch_recordings.py — run process_recording.py on every OBS recording stop.
Needs: pip install obsws-python  (OBS plugin: obs-websocket >= 5, Tools -> obs-websocket)

Environment (never hardcode the key):
  OBS_WEBSOCKET_KEY   password from OBS -> Tools -> obs-websocket
  OBS_RECORDINGS      folder where OBS writes recordings (default: ~/Movies)
  PROJECT             project name for output files (default: 'recording')
  WHISPER_BIN         optional path to whisper-cli; TRANSCRIBE=0 disables transcription
"""
import os, pathlib, subprocess, sys
import obsws_python as obsws

rec_dir = pathlib.Path(os.environ.get("OBS_RECORDINGS", str(pathlib.Path.home() / "Movies")))
script = pathlib.Path(__file__).parent / "process_recording.py"

def on_recording_stopped(event):
    newest = max(rec_dir.glob("*.mkv"), key=lambda p: p.stat().st_mtime, default=None)
    if newest is None:
        print(f"no .mkv in {rec_dir}, nothing to do", file=sys.stderr)
        return
    cmd = [sys.executable, str(script), str(newest),
           "--project", os.environ.get("PROJECT", "recording")]
    if os.environ.get("TRANSCRIBE", "1") == "1":
        cmd.append("--transcribe")
    if os.environ.get("WHISPER_BIN"):
        cmd += ["--whisper", os.environ["WHISPER_BIN"]]
    print(f"processing {newest}", flush=True)
    subprocess.run(cmd, check=True)

client = obsws.Client(host="localhost", port=4455,
                      password=os.environ["OBS_WEBSOCKET_KEY"])  # obsws-python 2.x style
client.add_event_callback("RecordOutputStopped", on_recording_stopped)  # OBS 28+ / obs-websocket 5
print("listening for RecordOutputStopped... (Ctrl-C to stop)")
client.run()