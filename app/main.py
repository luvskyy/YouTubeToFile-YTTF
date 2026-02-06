from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# Allow running `python app/main.py` without import issues.
if __name__ == "__main__" and __package__ is None:
    from pathlib import Path as _Path

    sys.path.append(str(_Path(__file__).resolve().parents[1]))

from app.downloader import DownloadRequest, format_status_line, run_download
from app.history import DownloadRecord, add_download, delete_download, load_history


APP_TITLE = "YouTube to File"
APP_SUBTITLE = "Download and convert videos instantly."

# Modern liquid glass color palette with grey/black base and red accents
COLOR_BG_PRIMARY = "#0a0a0a"      # Pure black base
COLOR_BG_SECONDARY = "#141414"    # Dark grey cards
COLOR_GLASS_LIGHT = "#2a2a2a"     # Translucent glass layer 1 (lighter for depth)
COLOR_GLASS_HOVER = "#353535"     # Translucent glass layer 2 (hover state)
COLOR_TEXT_PRIMARY = "#ffffff"    # Primary text
COLOR_TEXT_SECONDARY = "#8a8a8a"  # Grey text
COLOR_ACCENT = "#dc2626"          # Red accent (primary action)
COLOR_ACCENT_LIGHT = "#ef4444"    # Light red accent (hover)
COLOR_SUCCESS = "#34c759"         # Green success state
COLOR_ERROR = "#dc2626"           # Red error state (matches accent)
COLOR_BORDER = "#252525"          # Subtle border (darker for depth)


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
            unselected_color=COLOR_GLASS_LIGHT,
            unselected_hover_color=COLOR_GLASS_HOVER,
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
            hover_color=COLOR_GLASS_HOVER,
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

        # Tabbed view for Status Log and History
        tabview = ctk.CTkTabview(
            root,
            fg_color=COLOR_BG_SECONDARY,
            corner_radius=18,
            border_width=1,
            border_color=COLOR_BORDER,
            segmented_button_fg_color=COLOR_GLASS_LIGHT,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color=COLOR_ACCENT_LIGHT,
            segmented_button_unselected_color=COLOR_GLASS_LIGHT,
            segmented_button_unselected_hover_color=COLOR_GLASS_HOVER,
        )
        tabview.pack(fill="both", expand=True)

        # Tab 1: Status Log (preserve existing functionality)
        tab_log = tabview.add("Status Log")
        tab_log.grid_columnconfigure(0, weight=1)
        tab_log.grid_rowconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(
            tab_log,
            fg_color=COLOR_GLASS_LIGHT,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=10),
            border_width=0,
        )
        self.log_box.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.log_box.configure(state="disabled")
        self._log("Ready to download.")

        # Tab 2: History (new)
        tab_history = tabview.add("History")
        tab_history.grid_columnconfigure(0, weight=1)
        tab_history.grid_rowconfigure(0, weight=1)

        # Scrollable frame for history items
        self.history_scroll = ctk.CTkScrollableFrame(
            tab_history,
            fg_color="transparent",
        )
        self.history_scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        self.history_scroll.grid_columnconfigure(0, weight=1)

        # Warning labels at bottom
        history_warning = ctk.CTkLabel(
            tab_history,
            text="Showing last 50 downloads. Older items are automatically removed.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        history_warning.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 2))

        delete_info = ctk.CTkLabel(
            tab_history,
            text="Deleting from history does not remove the file from your computer.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        delete_info.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        # Load initial history
        self._refresh_history()

        # Store for later reference
        self._current_download_request: DownloadRequest | None = None

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
        self._current_download_request = req  # Store for history capture

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
                        # Capture download for history
                        self._capture_download_history()
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

    def _refresh_history(self) -> None:
        """Refresh the history display."""
        # Clear existing widgets
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        # Load history
        history = load_history()

        if not history:
            # Show empty state
            empty_label = ctk.CTkLabel(
                self.history_scroll,
                text="No downloads yet",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXT_SECONDARY,
            )
            empty_label.pack(pady=40)
            return

        # Display each history item (newest first)
        for record in reversed(history):
            self._create_history_item(record)

    def _create_history_item(self, record: DownloadRecord) -> None:
        """Create a single history item card."""
        # Card frame
        card = ctk.CTkFrame(
            self.history_scroll,
            fg_color=COLOR_GLASS_LIGHT,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.pack(fill="x", pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        # Title and timestamp row
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        header_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text=record.title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Timestamp
        try:
            time_str = datetime.fromisoformat(record.timestamp).strftime("%b %d, %Y %I:%M %p")
        except (ValueError, AttributeError):
            time_str = "Unknown"

        time_label = ctk.CTkLabel(
            header_frame,
            text=time_str,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="e",
        )
        time_label.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # Info row (format + size)
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        format_badge = "MP4" if "MP4" in record.mode else "MP3"
        size_str = self._format_file_size(record.file_size)

        info_label = ctk.CTkLabel(
            info_frame,
            text=f"{format_badge}  •  {size_str}",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        info_label.pack(side="left")

        # Status indicator (success/failed)
        if record.status == "success":
            status_text = "✓ Success"
            status_color = COLOR_SUCCESS
        else:
            status_text = "✗ Failed"
            status_color = COLOR_ERROR

        status_label = ctk.CTkLabel(
            info_frame,
            text=status_text,
            font=ctk.CTkFont(size=11),
            text_color=status_color,
            anchor="e",
        )
        status_label.pack(side="right")

        # Action buttons row
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        # Open file button
        btn_open = ctk.CTkButton(
            btn_frame,
            text="Open",
            width=80,
            height=28,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GLASS_HOVER,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._open_file(record.filepath),
        )
        btn_open.pack(side="left", padx=(0, 8))

        # Show in folder button
        btn_folder = ctk.CTkButton(
            btn_frame,
            text="Show in Folder",
            width=120,
            height=28,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GLASS_HOVER,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._show_in_folder(record.filepath),
        )
        btn_folder.pack(side="left", padx=(0, 8))

        # Copy URL button
        btn_copy = ctk.CTkButton(
            btn_frame,
            text="Copy URL",
            width=90,
            height=28,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GLASS_HOVER,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._copy_url(record.url),
        )
        btn_copy.pack(side="left", padx=(0, 8))

        # Delete file button
        btn_delete_file = ctk.CTkButton(
            btn_frame,
            text="Delete File",
            width=90,
            height=28,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GLASS_HOVER,
            hover_color=COLOR_ERROR,
            text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._delete_file(record.filepath, record.id),
        )
        btn_delete_file.pack(side="right", padx=(8, 0))

        # Delete history button
        btn_delete = ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=70,
            height=28,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GLASS_HOVER,
            hover_color=COLOR_ERROR,
            text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._delete_history_item(record.id),
        )
        btn_delete.pack(side="right")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _open_file(self, filepath: str) -> None:
        """Open file with default application."""
        path = Path(filepath)
        if not path.exists():
            self._log("✗ File no longer exists")
            return

        try:
            if os.name == "nt":  # Windows
                os.startfile(filepath)
            elif os.name == "posix":  # macOS/Linux
                subprocess.run(
                    ["open" if sys.platform == "darwin" else "xdg-open", filepath],
                    check=False,
                )
            self._log(f"✓ Opened: {path.name}")
        except Exception as e:
            self._log(f"✗ Could not open file: {e}")

    def _show_in_folder(self, filepath: str) -> None:
        """Show file in File Explorer/Finder."""
        path = Path(filepath)
        if not path.exists():
            self._log("✗ File no longer exists")
            return

        try:
            if os.name == "nt":  # Windows
                subprocess.run(["explorer", "/select,", str(path)], check=False)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", "-R", str(path)], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", str(path.parent)], check=False)
            self._log(f"✓ Showed in folder: {path.name}")
        except Exception as e:
            self._log(f"✗ Could not show in folder: {e}")

    def _copy_url(self, url: str) -> None:
        """Copy URL to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(url)
        self._log("✓ URL copied to clipboard")

    def _delete_history_item(self, record_id: str) -> None:
        """Delete a history item and refresh display."""
        delete_download(record_id)
        self._refresh_history()
        self._log("✓ History item deleted")

    def _delete_file(self, filepath: str, record_id: str) -> None:
        """Delete file from filesystem and remove from history."""
        path = Path(filepath)
        try:
            if path.exists():
                path.unlink()
                self._log(f"✓ File deleted: {path.name}")
            else:
                self._log(f"✗ File not found: {path.name}")

            # Also remove from history
            delete_download(record_id)
            self._refresh_history()
        except PermissionError:
            self._log(f"✗ Permission denied: Cannot delete {path.name}")
        except Exception as e:
            self._log(f"✗ Could not delete file: {e}")

    def _capture_download_history(self) -> None:
        """Capture the just-completed download to history."""
        if not self._current_download_request:
            return

        req = self._current_download_request

        # Find the downloaded file (most recent in save_dir)
        try:
            files = list(req.save_dir.glob("*"))
            if not files:
                return

            # Get most recent file
            latest_file = max(files, key=lambda p: p.stat().st_mtime)

            # Extract title from filename
            title = latest_file.stem

            # Create history record
            record = DownloadRecord(
                url=req.url,
                title=title,
                filename=latest_file.name,
                filepath=str(latest_file),
                mode=req.mode,
                file_size=latest_file.stat().st_size,
                status="success",
                error_message=None,
            )

            # Save to history
            add_download(record)

            # Refresh history display
            self._refresh_history()

        except Exception as e:
            self._log(f"Warning: Could not save to history: {e}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

