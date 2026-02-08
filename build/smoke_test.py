from __future__ import annotations

import queue
import shutil
from pathlib import Path

import sys

# Ensure imports work when running from build/ directory.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.downloader import DownloadRequest, run_download


DEFAULT_TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # Me at the zoo (usually available)
OUT_DIR = Path(".tmp_smoke").resolve()


def run(mode: str) -> None:
    q: "queue.Queue[dict]" = queue.Queue()
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_URL
    req = DownloadRequest(url=url, save_dir=OUT_DIR, mode=mode)
    run_download(req, q)

    logs: list[str] = []
    ok: bool | None = None

    while True:
        evt = q.get()
        if evt.get("type") == "log":
            logs.append(str(evt.get("message")))
        if evt.get("type") == "done":
            ok = bool(evt.get("ok"))
            break

    print()
    print(f"MODE: {mode}")
    print(f"OK: {ok}")
    if logs:
        print(f"LAST_LOG: {logs[-1]}")

    if not ok:
        raise SystemExit(f"Smoke test failed for mode: {mode}")


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run("Best Video (MP4)")
    run("Audio Only (MP3)")

    mp4s = list(OUT_DIR.glob("*.mp4"))
    mp3s = list(OUT_DIR.glob("*.mp3"))
    print()
    print(f"Downloaded files in {OUT_DIR}:")
    print(f"- MP4 count: {len(mp4s)}")
    print(f"- MP3 count: {len(mp3s)}")

    if not mp4s:
        raise SystemExit("Expected at least one .mp4 output file.")
    if not mp3s:
        raise SystemExit("Expected at least one .mp3 output file.")

    print()
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
