# YouTube to File / YTDL

A private locally ran youtube video / audio (MP4/MP3) downloader. Download as much as you want without Youtube Premium and without the risk of malicious websites!

## How to use

- Run the installer
- Paste a YouTube URL
- Choose output:
  - **(MP4)** (video)
  - **(MP3)** (audio)
- Choose a custom save folder
- Real-time progress bar + status log
- Video preview
- Download history tab
- Manage downloads in the app
- Download runs in a background thread

## Windows (easiest install)
Simply download the installer in the releases tab.

## Run from source (macOS/Linux)

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

## Notes

- The build script automatically downloads a Windows FFmpeg “essentials” zip and copies `ffmpeg.exe` + `ffprobe.exe` into `assets\\ffmpeg\\` before building.\n- If you’re behind a proxy or downloads are blocked, you can manually place `ffmpeg.exe` and `ffprobe.exe` into `assets\\ffmpeg\\` and rerun the build.
