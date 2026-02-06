# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube to File is a Windows GUI application built with **customtkinter** (modern, dark UI) and **yt-dlp** (video/audio downloading). The app bundles FFmpeg and is packaged as a standalone `.exe` using PyInstaller, with an optional Inno Setup installer.

### Key Technologies
- **UI Framework**: customtkinter (Python)
- **Downloader**: yt-dlp (supports YouTube and many other video platforms)
- **Packager**: PyInstaller (bundles Python + dependencies into .exe)
- **Installer**: Inno Setup (optional, for distribution)

## Architecture

### Core Components

1. **`app/main.py`** - Application entry point
   - Defines the `App` class extending `ctk.CTk` (customtkinter window)
   - Builds the UI: URL input, format selector, folder chooser, download button, progress bar, status log
   - Manages threading: spawns a download thread when user clicks Download
   - Event polling loop: reads from `_event_queue` (thread-safe queue) every 100ms to update UI from background thread
   - State management: `_is_downloading` flag prevents multiple concurrent downloads

2. **`app/downloader.py`** - Download logic and yt-dlp integration
   - `DownloadRequest`: dataclass holding URL, save directory, and mode ("Best Video (MP4)" or "Audio Only (MP3)")
   - `QueueLogger`: custom logger that pushes yt-dlp messages into the event queue instead of stdout
   - `build_ydl_options()`: constructs yt-dlp configuration based on mode:
     - **MP4**: Uses `format: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"` and merges with `merge_output_format: "mp4"`
     - **MP3**: Uses `format: "bestaudio/best"` with FFmpeg post-processor to extract audio and encode as 192kbps mp3
   - `progress_hook()`: called by yt-dlp during download, emits progress events (downloaded bytes, total, speed, ETA)
   - `run_download()`: main blocking function that runs yt-dlp; designed to be called in a background thread
   - `format_status_line()`: formats a single-line status string from progress event (percentage, size, speed, ETA)

3. **`app/resources.py`** - Resource path resolution
   - `project_root()`: returns repo root in dev mode or PyInstaller's temp extraction directory (`sys._MEIPASS`)
   - `ffmpeg_dir()`: returns `assets/ffmpeg` path (where bundled ffmpeg.exe and ffprobe.exe reside)

### Threading Model

- **Main thread**: Tkinter event loop and UI updates
- **Download thread**: Background thread spawned by `_on_download()` that calls `run_download()`, communicates via `_event_queue`
- **Thread safety**: Uses `queue.Queue` (thread-safe) for UI → download thread communication; polling loop prevents race conditions
- **UI blocking**: Download button and other inputs are disabled during download (`_set_busy()`)

### Asset Management

- **FFmpeg binaries**: Must be placed in `assets/ffmpeg/` (ffmpeg.exe and ffprobe.exe)
- **Build script**: Automatically downloads FFmpeg during build; must be present before building
- **PyInstaller spec**: Bundles `assets/ffmpeg/` into the .exe if it exists

## Development Setup

### Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -U pip
pip install -r requirements.txt
```

### Running from Source

```bash
python app/main.py
```

The script detects when run as `__main__` and adjusts `sys.path` to allow imports of the `app` module.

## Building

### Build Requirements
- Windows (build script is PowerShell)
- Python 3.8+
- PyInstaller (in `requirements.txt`)
- FFmpeg binaries in `assets/ffmpeg/` (ffmpeg.exe and ffprobe.exe)
- Inno Setup 6 (optional, for installer)

### Build Executable

```powershell
.\build\build.ps1
```

This script:
1. Creates/activates venv
2. Installs dependencies
3. Verifies FFmpeg binaries exist in `assets/ffmpeg/`
4. Runs PyInstaller using `build/yt_to_file.spec`
5. Outputs: `dist/YouTubeToFile/YouTubeToFile.exe`

### Build Installer (Optional)

The build script also runs Inno Setup if available:
- Requires Inno Setup 6 installed in `Program Files (x86)/Inno Setup 6/`
- Outputs: `installer/Output/YouTubeToFile-Setup.exe`

## Testing

### Smoke Test

```bash
python build/smoke_test.py [optional_youtube_url]
```

Default test URL: `https://www.youtube.com/watch?v=jNQXAC9IVRw` (Me at the zoo)

The test:
- Creates temporary directory `.tmp_smoke/`
- Downloads in both modes (MP4 and MP3) using `run_download()` directly
- Verifies at least one .mp4 and one .mp3 are created
- Cleans up on success

## Key Design Patterns

### Event-Driven UI Updates
Instead of blocking or using callbacks that run on the download thread, events are queued and polled on the main thread. This avoids Tkinter thread-safety issues.

Event types in queue:
- `{"type": "log", "message": str}` - Add message to status log
- `{"type": "progress", "value": float, "downloaded": int, "total": int, "speed": float, "eta": float}` - Update progress bar
- `{"type": "done", "ok": bool}` - Download finished; re-enable UI

### FFmpeg Location Handling
Both in dev and in the bundled .exe, `ffmpeg_dir()` resolves the correct path. The spec file ensures `assets/ffmpeg/` is bundled. At runtime, `build_ydl_options()` passes the FFmpeg path to yt-dlp so it doesn't need to be on PATH.

### Resource Path Resolution
`app/resources.py` provides a single source of truth for resolving paths, accounting for PyInstaller's temporary extraction directory.

## Common Issues & Solutions

### FFmpeg Not Found
- **Problem**: "FFmpeg is required for MP3 conversion but was not found"
- **Solution**: Download FFmpeg from https://ffmpeg.org/download.html (Windows "essentials" build), extract ffmpeg.exe and ffprobe.exe to `assets/ffmpeg/`

### Import Errors When Running from Source
- **Problem**: `ModuleNotFoundError: No module named 'app'`
- **Solution**: Run as `python app/main.py` from repo root (the script handles sys.path)

### Build Fails with PyInstaller
- **Problem**: "PyInstaller failed"
- **Solution**: Ensure FFmpeg is in `assets/ffmpeg/` and venv is activated

## Files Reference

- `app/main.py` - UI and main application
- `app/downloader.py` - Download logic, yt-dlp integration, progress handling
- `app/resources.py` - Path resolution utilities
- `app/__init__.py` - Package marker
- `build/build.ps1` - Windows build script
- `build/yt_to_file.spec` - PyInstaller specification
- `build/smoke_test.py` - Integration test
- `build/yt_to_file/` - PyInstaller cache/build artifacts
- `assets/ffmpeg/` - FFmpeg binaries (must be populated before building)
- `installer/YouTubeToFile.iss` - Inno Setup installer configuration
- `requirements.txt` - Python dependencies
- `README.md` - User-facing documentation
