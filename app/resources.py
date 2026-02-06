from __future__ import annotations

import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    """
    Returns the project root directory.

    - In dev: <repo_root>
    - In PyInstaller: sys._MEIPASS (temp extraction directory)
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))  # type: ignore[no-any-return]
    # app/resources.py -> app/ -> repo_root
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str | Path) -> Path:
    return project_root() / Path(relative_path)


def ffmpeg_dir() -> Path:
    """Return the directory containing ffmpeg binaries.

    Checks bundled assets/ffmpeg/ first, then falls back to
    the system PATH (e.g. Homebrew on macOS).
    """
    bundled = resource_path(Path("assets") / "ffmpeg")
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if (bundled / ffmpeg_name).exists():
        return bundled

    # Fall back to system-installed ffmpeg
    which = shutil.which("ffmpeg")
    if which:
        return Path(which).parent

    return bundled

