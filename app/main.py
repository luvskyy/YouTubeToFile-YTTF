from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# Allow running `python app/main.py` without import issues.
if __name__ == "__main__" and __package__ is None:
    import sys
    from pathlib import Path as _Path

    sys.path.append(str(_Path(__file__).resolve().parents[1]))

from app.downloader import DownloadRequest, format_status_line, run_download


APP_TITLE = "YouTube to File"
APP_SUBTITLE = "Download and convert videos instantly."

# Modern liquid glass color palette (inspired by Apple design)
COLOR_BG_PRIMARY = "#0f1419"      # Deep dark background
COLOR_BG_SECONDARY = "#1a202d"    # Card background
COLOR_GLASS_LIGHT = "#2a3549"     # Light glass effect
COLOR_TEXT_PRIMARY = "#ffffff"    # Primary text
COLOR_TEXT_SECONDARY = "#b3b8c2"  # Secondary text
COLOR_ACCENT = "#6b9bef"          # Blue accent (primary action)
COLOR_ACCENT_LIGHT = "#8db3ff"    # Light blue accent (hover)
COLOR_SUCCESS = "#34c759"         # Green success state
COLOR_ERROR = "#ff3b30"           # Red error state
COLOR_BORDER = "#3a4556"          # Subtle borders


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("Dark")
        # Use blue theme but override with custom colors
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry("900x700")
        self.minsize(800, 650)

        # Set custom window background color
        self.configure(fg_color=COLOR_BG_PRIMARY)

        self._event_queue: "queue.Queue[dict]" = queue.Queue()
        self._download_thread: threading.Thread | None = None
        self._is_downloading = False

        self._build_ui()

        # Start queue polling loop
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        # Main container with padding
        root = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        root.pack(fill="both", expand=True, padx=24, pady=28)

        # Header Section
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", pady=(0, 32))

        title = ctk.CTkLabel(
            header,
            text=APP_TITLE,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text=APP_SUBTITLE,
            font=ctk.CTkFont(size=14),
            text_color=COLOR_TEXT_SECONDARY,
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        # Main input card with glass morphism effect
        card = ctk.CTkFrame(
            root,
            fg_color=COLOR_BG_SECONDARY,
            corner_radius=18,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.pack(fill="x", pady=(0, 20))

        card.grid_columnconfigure(0, weight=1)

        # URL Input Section
        url_label = ctk.CTkLabel(
            card,
            text="YouTube URL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        url_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        self.url_entry = ctk.CTkEntry(
            card,
            height=46,
            placeholder_text="Paste your YouTube link here…",
            font=ctk.CTkFont(size=13),
            fg_color=COLOR_GLASS_LIGHT,
            border_color=COLOR_BORDER,
            border_width=1,
            text_color=COLOR_TEXT_PRIMARY,
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        # Divider line
        divider1 = ctk.CTkFrame(card, fg_color=COLOR_BORDER, height=1)
        divider1.grid(row=2, column=0, sticky="ew", padx=20, pady=0)

        # Format and Folder Section
        options_frame = ctk.CTkFrame(card, fg_color="transparent")
        options_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)

        # Format selector (left side)
        fmt_label = ctk.CTkLabel(
            options_frame,
            text="Format",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        fmt_label.grid(row=0, column=0, sticky="w")

        self.format_selector = ctk.CTkSegmentedButton(
            options_frame,
            values=["MP4 Video", "MP3 Audio"],
            height=34,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_GLASS_LIGHT,
            selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_LIGHT,
            unselected_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
        )
        self.format_selector.set("MP4 Video")
        self.format_selector.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        # Save folder section (right side)
        folder_label = ctk.CTkLabel(
            options_frame,
            text="Save to",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        folder_label.grid(row=0, column=1, sticky="w", padx=(20, 0))

        self.save_dir = Path.home() / "Downloads"
        self.folder_value = ctk.CTkLabel(
            options_frame,
            text=self._truncate_path(str(self.save_dir), 40),
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.folder_value.grid(row=1, column=1, sticky="ew", padx=(20, 0), pady=(6, 0))

        self.folder_button = ctk.CTkButton(
            options_frame,
            text="Browse",
            width=100,
            height=34,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_GLASS_LIGHT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            command=self._choose_folder,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        self.folder_button.grid(row=1, column=1, sticky="e", padx=(20, 0), pady=(6, 0))

        # Download button
        self.download_button = ctk.CTkButton(
            card,
            text="Download",
            height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_LIGHT,
            text_color="#ffffff",
            command=self._on_download,
            corner_radius=12,
            border_width=0,
        )
        self.download_button.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))

        # Progress section with glass morphism
        progress_card = ctk.CTkFrame(
            root,
            fg_color=COLOR_BG_SECONDARY,
            corner_radius=18,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        progress_card.pack(fill="x", pady=(0, 20))
        progress_card.grid_columnconfigure(0, weight=1)

        # Progress bar with custom styling
        self.progress = ctk.CTkProgressBar(
            progress_card,
            fg_color=COLOR_GLASS_LIGHT,
            progress_color=COLOR_ACCENT,
            height=6,
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        self.progress.set(0.0)

        self.status_line = ctk.CTkLabel(
            progress_card,
            text="Ready to download.",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.status_line.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        # Status log section
        log_card = ctk.CTkFrame(
            root,
            fg_color=COLOR_BG_SECONDARY,
            corner_radius=18,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        log_card.pack(fill="both", expand=True)
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_label = ctk.CTkLabel(
            log_card,
            text="Status Log",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        log_label.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 10))

        self.log_box = ctk.CTkTextbox(
            log_card,
            fg_color=COLOR_GLASS_LIGHT,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=10),
            border_width=0,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.log_box.configure(state="disabled")
        self._log("Ready to download.")

    def _truncate_path(self, path: str, max_len: int) -> str:
        """Truncate path to max_len characters, showing end of path."""
        if len(path) <= max_len:
            return path
        # Show ".../(last part)"
        return "..." + path[-(max_len - 3):]

    def _set_busy(self, busy: bool) -> None:
        self._is_downloading = busy
        state = "disabled" if busy else "normal"

        self.url_entry.configure(state=state)
        self.format_selector.configure(state=state)
        self.folder_button.configure(state=state)
        self.download_button.configure(state=state)

        if busy:
            self.download_button.configure(
                text="Downloading…",
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT,
            )
        else:
            self.download_button.configure(
                text="Download",
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_LIGHT,
            )

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose Save Location")
        if not folder:
            return
        self.save_dir = Path(folder)
        self.folder_value.configure(text=self._truncate_path(str(self.save_dir), 40))
        self._log(f"✓ Save location updated")

    def _on_download(self) -> None:
        if self._is_downloading:
            return

        url = self.url_entry.get().strip()
        if not url:
            self._log("✗ Error: Please paste a YouTube URL.")
            return

        if not self.save_dir.exists():
            self._log("✗ Error: Save location does not exist. Choose a valid folder.")
            return

        mode = self.format_selector.get()
        # Convert format selector text back to original mode names
        mode_map = {"MP4 Video": "Best Video (MP4)", "MP3 Audio": "Audio Only (MP3)"}
        actual_mode = mode_map.get(mode, "Best Video (MP4)")
        req = DownloadRequest(url=url, save_dir=self.save_dir, mode=actual_mode)

        self.progress.set(0.0)
        self.status_line.configure(text="Starting download…", text_color=COLOR_TEXT_SECONDARY)
        self._set_busy(True)
        self._log("⬇ Starting download…")

        self._download_thread = threading.Thread(
            target=run_download,
            args=(req, self._event_queue),
            daemon=True,
        )
        self._download_thread.start()

    def _poll_events(self) -> None:
        try:
            while True:
                evt = self._event_queue.get_nowait()
                et = evt.get("type")
                if et == "log":
                    self._log(str(evt.get("message", "")))
                elif et == "progress":
                    value = float(evt.get("value", 0.0))
                    self.progress.set(max(0.0, min(1.0, value)))
                    self.status_line.configure(text=format_status_line(evt), text_color=COLOR_TEXT_SECONDARY)
                elif et == "done":
                    ok = bool(evt.get("ok", False))
                    self._set_busy(False)
                    if ok:
                        self.progress.set(1.0)
                        self.status_line.configure(text="✓ Download complete!", text_color=COLOR_SUCCESS)
                        self._log("✓ Download complete!")
                    else:
                        self.status_line.configure(text="✗ Download failed. Check log.", text_color=COLOR_ERROR)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_events)

    def _log(self, message: str) -> None:
        msg = (message or "").strip()
        if not msg:
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

