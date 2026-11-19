# VirlClipX AI Gaming Clipper

A self-hostable starter website for creating vertical gaming clips from YouTube videos that you own or are explicitly authorized to download, edit and repost.

## What works in this MVP
- Mobile-friendly web UI (works in Android Chrome when hosted).
- YouTube URL input via `yt-dlp` (publicly accessible videos only; no DRM/access-control bypass).
- Automatically selects candidate moments using audio activity peaks.
- Renders 9:16, 1080x1920 MP4 clips with FFmpeg.
- Downloads generated clips from the website.

## Important limitations
- This is an MVP, not a human-level AI editor. It uses audio energy as a highlight heuristic; loud moments are not always the best moments. It does not yet generate speech captions or understand game events.
- A YouTube URL does not grant permission to download or repost the video. Use your own footage or obtain explicit permission and check platform terms and applicable law.
- Software is open source and has no per-clip API charge, but hosting, bandwidth, storage and CPU/GPU can cost money. Free hosting providers commonly sleep, limit processing time, or disallow heavy video workloads. There is no honest guarantee of unlimited free cloud processing.
- Job state is in memory and generated files are temporary. Restarting the server clears job status.

## Run locally
Requires Python 3.11+, FFmpeg and FFprobe.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` on the computer. To use it from an Android phone on the same Wi-Fi, open `http://COMPUTER-LAN-IP:8000`.

## Docker

```bash
docker build -t virlclipx .
docker run --rm -p 8000:8000 -v virlclipx-data:/tmp/virlclipx virlclipx
```

## Production hardening before public launch
Add authentication, per-user quotas, a persistent job queue, file retention/deletion, rate limits, URL allowlisting, worker isolation, disk limits, monitoring and a clear takedown/contact process. Do not expose an unrestricted downloader to the public internet.
