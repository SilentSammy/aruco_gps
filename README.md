# ArUco GPS

Camera-based ArUco pose tracking, optional ball detection, visualization,
camera streaming, and UDP telemetry for multiple robot projects.

## Install and run

Clone this repository, then run `bash setup.sh` on Linux or `./setup.ps1` in
PowerShell on Windows. Add `--yes` (Linux) or `-Yes` (Windows) to skip the
confirmation. The vision service currently has a Linux launcher:

```bash
bash run.sh
```

The launcher prompts for a setup and ball detection, runs camera capture and
pose tracking in one terminal, and stops its child processes on Ctrl+C. Pass
`--setup setup_160cm --ball-detection` to skip those prompts. Network setup is
separate; this project never configures a hotspot.

Default telemetry uses UDP port 5000 broadcast and unicast subscriptions on
port 5001. The launcher broadcasts to `255.255.255.255` unless a specific
address is supplied, e.g. `bash run.sh --broadcast 192.168.12.255`.
Clients send `POSE_SUBSCRIBE` once per second to port 5001 from the socket
that receives data; send `POSE_UNSUBSCRIBE` when finished. The legacy packet
format and broadcast feed remain compatible with existing robot firmware.

Use `python telemetry_listener.py --server HOST` to inspect unicast, or omit
`--server` for broadcast. The camera viewer is available at `http://HOST:8080/`;
it has no built-in authentication, so restrict network access as appropriate.

`vision_setup.py` defines cameras, calibrations, boards and named setups.
`marker_config.json` controls per-marker appearance and height and reloads
while running. `ball_thresholds.txt` sets optional ball detection thresholds.
The provided setup reflects the lab camera; other installations need their own
calibration and board settings. See `python main.py --help` and
`python camera_stream.py --run-vision --help` for additional options.

For a camera-free smoke test:

```bash
.venv/bin/python camera_stream.py --run-vision --synthetic-camera --stream-port 0 --headless --max-frames 30
```

TE2004 and VSSS may pin this repo as a Git submodule. A single running service
can serve both projects simultaneously; consumers need not launch a camera.
