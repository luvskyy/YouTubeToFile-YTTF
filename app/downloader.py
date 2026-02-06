from __future__ import annotations

import os
import queue
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

from app.resources import ffmpeg_dir


DownloadEvent = dict[str, Any]


class QueueLogger:
    def __init__(self, event_queue: "queue.Queue[DownloadEvent]"):
        self._q = event_queue

    def debug(self, msg: str) -> None:
        # yt-dlp can be noisy; we keep debug mostly silent
        pass

    def info(self, msg: str) -> None:
        self._q.put({"type": "log", "message": msg})

    def warning(self, msg: str) -> None:
        self._q.put({"type": "log", "message": f"Warning: {msg}"})

    def error(self, msg: str) -> None:
        self._q.put({"type": "log", "message": f"Error: {msg}"})


def _format_bytes(num: float | None) -> str:
    if not num or num <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    n = float(num)
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    if i == 0:
        return f"{int(n)} {units[i]}"
    return f"{n:.2f} {units[i]}"


def _format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    save_dir: Path
    mode: str  # "Best Video (MP4)" | "Audio Only (MP3)"


def build_ydl_options(
    req: DownloadRequest,
    event_queue: "queue.Queue[DownloadEvent]",
) -> dict[str, Any]:
    save_dir = str(req.save_dir)

    ff_dir = ffmpeg_dir()
    ffmpeg_location = str(ff_dir) if ff_dir.exists() else None

    def progress_hook(d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed")
            eta = d.get("eta")

            progress = (downloaded / total) if total else 0.0
            progress = max(0.0, min(1.0, float(progress)))

            event_queue.put(
                {
                    "type": "progress",
                    "value": progress,
                    "downloaded": downloaded,
                    "total": total,
                    "speed": speed,
                    "eta": eta,
                }
            )
        elif status == "finished":
            filename = d.get("filename")
            event_queue.put({"type": "progress", "value": 1.0})
            if filename:
                event_queue.put({"type": "log", "message": f"Downloaded: {filename}"})
            event_queue.put({"type": "log", "message": "Finalizing..."})

    common: dict[str, Any] = {
        "outtmpl": os.path.join(save_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "logger": QueueLogger(event_queue),
        # Keep output quiet; we push our own messages to the UI.
        "quiet": True,
        "no_warnings": True,
    }

    if ffmpeg_location:
        common["ffmpeg_location"] = ffmpeg_location

    if req.mode == "Audio Only (MP3)":
        common.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    else:
        common.update(
            {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            }
        )

    return common


def run_download(
    req: DownloadRequest,
    event_queue: "queue.Queue[DownloadEvent]",
    stop_check: Callable[[], bool] | None = None,
) -> None:
    """
    Runs yt_dlp download. This is designed to be called inside a background thread.
    Communicates back to the UI using event_queue.
    """
    try:
        event_queue.put({"type": "log", "message": "Starting download..."})

        if req.mode == "Audio Only (MP3)":
            event_queue.put({"type": "log", "message": "Mode: Audio Only (MP3)"})
            ff_dir = ffmpeg_dir()
            ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
            if not (ff_dir / ffmpeg_name).exists():
                raise FileNotFoundError(
                    "FFmpeg is required for MP3 conversion but was not found. "
                    "Install FFmpeg (e.g. 'brew install ffmpeg' on macOS) or "
                    "place ffmpeg binaries in assets/ffmpeg/."
                )
        else:
            event_queue.put({"type": "log", "message": "Mode: Best Video (MP4)"})

        if not req.save_dir.exists():
            raise FileNotFoundError(f"Save folder does not exist: {req.save_dir}")

        opts = build_ydl_options(req, event_queue)

        last_stop_poll = 0.0

        def _progress_passthrough(d: dict[str, Any]) -> None:
            nonlocal last_stop_poll
            now = time.time()
            if stop_check and (now - last_stop_poll) >= 0.5:
                last_stop_poll = now
                if stop_check():
                    raise RuntimeError("Cancelled")

        # Add a tiny hook to enable optional cancel checks without changing UI.
        opts["progress_hooks"] = list(opts.get("progress_hooks", [])) + [_progress_passthrough]

        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        event_queue.put({"type": "log", "message": "Finished!"})
        event_queue.put({"type": "done", "ok": True})
    except Exception as e:
        event_queue.put({"type": "log", "message": f"Error: {e}"})
        event_queue.put({"type": "done", "ok": False})


def format_status_line(evt: DownloadEvent) -> str:
    """
    Formats a single-line status for the UI from a progress event.
    """
    downloaded = evt.get("downloaded") or 0
    total = evt.get("total") or 0
    speed = evt.get("speed")
    eta = evt.get("eta")
    pct = int(round((evt.get("value") or 0.0) * 100))

    left = f"{pct:3d}%  {_format_bytes(downloaded)}"
    if total:
        left += f" / {_format_bytes(total)}"

    right_parts: list[str] = []
    if speed:
        right_parts.append(f"{_format_bytes(speed)}/s")
    if eta is not None:
        right_parts.append(f"ETA {_format_eta(float(eta))}")

    right = "  •  ".join(right_parts) if right_parts else ""
    return f"{left}" + (f"    {right}" if right else "")

