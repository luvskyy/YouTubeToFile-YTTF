# YouTube to File (Windows GUI)

A modern Windows GUI downloader built with **customtkinter** + **yt-dlp**, packaged as a **.exe** with **bundled FFmpeg** for MP3 extraction.

## Features

- Dark, professional UI (customtkinter **Dark** + **blue** theme)
- Paste a YouTube URL
- Choose output:
  - **Best Video (MP4)** (merges video + audio)
  - **Audio Only (MP3)** (extracts + converts to mp3)
- Choose a save folder
- Real-time progress bar + status log
- Download runs in a background thread (UI stays responsive)

## Run from source (dev)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt

python app\main.py
```

## Build a Windows .exe (PyInstaller)

```powershell
.\build\build.ps1
```

Output:\n- `dist\\YouTubeToFile\\YouTubeToFile.exe`

## Build a one-click installer (Setup .exe)

1. Install **Inno Setup 6** (includes `ISCC.exe`).\n2. Run the same build script:

```powershell
.\build\build.ps1
```

Installer output:\n- `installer\\Output\\YouTubeToFile-Setup.exe`

## Notes

- The build script automatically downloads a Windows FFmpeg “essentials” zip and copies `ffmpeg.exe` + `ffprobe.exe` into `assets\\ffmpeg\\` before building.\n- If you’re behind a proxy or downloads are blocked, you can manually place `ffmpeg.exe` and `ffprobe.exe` into `assets\\ffmpeg\\` and rerun the build.
