from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class DownloadRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    url: str = ""
    title: str = ""
    filename: str = ""
    filepath: str = ""
    mode: str = ""  # "Best Video (MP4)" or "Audio Only (MP3)"
    file_size: int = 0  # bytes
    status: str = "success"  # "success" or "failed"
    error_message: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> DownloadRecord:
        """Create DownloadRecord from dictionary."""
        return cls(**data)

    def to_dict(self) -> dict:
        """Convert DownloadRecord to dictionary."""
        return asdict(self)


def get_history_path() -> Path:
    """Returns path to history.json in user data directory."""
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"

    data_dir = base / "YouTubeToFile"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # Fall back to temp directory if we can't create user data dir
        import tempfile

        temp_dir = Path(tempfile.gettempdir()) / "YouTubeToFile"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir / "history.json"

    return data_dir / "history.json"


def load_history() -> list[DownloadRecord]:
    """Load history from JSON file, returns empty list if not found/corrupted."""
    history_file = get_history_path()

    if not history_file.exists():
        return []

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        records = []
        for item in data:
            if isinstance(item, dict):
                try:
                    record = DownloadRecord.from_dict(item)
                    records.append(record)
                except (TypeError, ValueError):
                    # Skip corrupted records
                    continue

        return records
    except (json.JSONDecodeError, IOError) as e:
        # Log would happen at call site
        return []


def save_history(records: list[DownloadRecord]) -> None:
    """Save history to JSON file, keeps only last 50 entries."""
    history_file = get_history_path()

    # Keep only last 50 entries
    records = records[-50:]

    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)
    except IOError as e:
        # Caller should handle logging
        pass


def add_download(record: DownloadRecord) -> None:
    """Add a new download record and save (auto-limits to 50)."""
    history = load_history()
    history.append(record)
    save_history(history)


def delete_download(record_id: str) -> None:
    """Delete a download record by ID."""
    history = load_history()
    history = [r for r in history if r.id != record_id]
    save_history(history)
