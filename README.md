# YouTube to File / YTTF

A private locally ran youtube video / audio (MP4/MP3) downloader. Download as much as you want without Youtube Premium and without the risk of malicious websites!

## How to use

- Run the installer
- Paste a YouTube URL
- Choose output:
  - **(MP4)** (video)
  - **(MP3)** (audio)
- Choose a save location
- Hit download!

## Features

- Real-time progress bar + status log
- Video preview
- Download history tab (last 50)
- Manage downloads in the app
- Download runs in a background thread

## Windows (easiest install)

Simply download the installer in releases.

## Run from source (macOS/Linux)

*Fix coming next update

## Build a Windows .exe (PyInstaller)

```powershell
.\build\build.ps1
```

Output: `dist\\YouTubeToFile\\YouTubeToFile.exe`

## Notes

- The build script automatically downloads a Windows FFmpeg “essentials” zip and copies `ffmpeg.exe` + `ffprobe.exe` into `assets\\ffmpeg\\` before building. If you’re behind a proxy or downloads are blocked, you can manually place `ffmpeg.exe` and `ffprobe.exe` into `assets\\ffmpeg\\` and rerun the build.
