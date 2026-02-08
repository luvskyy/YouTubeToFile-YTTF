from __future__ import annotations

import io
import os
import queue
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

# Allow running `python app/main.py` without import issues.
if __name__ == "__main__" and __package__ is None:
    from pathlib import Path as _Path

    sys.path.append(str(_Path(__file__).resolve().parents[1]))

from app.downloader import DownloadRequest, VideoInfo, fetch_video_info, format_status_line, run_download
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


# ---------------------------------------------------------------------------
# Colour interpolation helpers (used by AnimatedToggle and App)
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return (
        f"#{int(r1 + (r2 - r1) * t):02x}"
        f"{int(g1 + (g2 - g1) * t):02x}"
        f"{int(b1 + (b2 - b1) * t):02x}"
    )


# ---------------------------------------------------------------------------
# Animated toggle widget with colour crossfade
# ---------------------------------------------------------------------------

class AnimatedToggle(ctk.CTkFrame):
    """Two-button toggle with smooth colour crossfade between options."""

    _ANIM_MS = 200   # total crossfade duration
    _ANIM_FRAMES = 12  # interpolation steps

    def __init__(
        self,
        master,
        values: list[str],
        height: int = 34,
        font=None,
        fg_color=COLOR_GLASS_LIGHT,
        selected_color=COLOR_ACCENT,
        text_color=COLOR_TEXT_PRIMARY,
        corner_radius: int = 8,
        **kwargs,
    ):
        super().__init__(
            master, fg_color=fg_color, corner_radius=corner_radius,
            height=height, **kwargs,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._values = list(values)
        self._selected_idx = 0
        self._animating = False
        self._disabled = False
        self._sel_color = selected_color
        self._unsel_color = fg_color

        # Inner padding frame
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=3, pady=3)
        for i in range(len(values)):
            inner.grid_columnconfigure(i, weight=1)
        inner.grid_rowconfigure(0, weight=1)

        self._btns: list[ctk.CTkButton] = []
        for i, val in enumerate(values):
            is_sel = i == 0
            btn = ctk.CTkButton(
                inner,
                text=val,
                font=font,
                fg_color=selected_color if is_sel else fg_color,
                hover_color=COLOR_ACCENT_LIGHT if is_sel else COLOR_GLASS_HOVER,
                text_color=text_color,
                corner_radius=max(corner_radius - 3, 4),
                border_width=0,
                command=lambda idx=i: self._on_click(idx),
            )
            btn.grid(row=0, column=i, sticky="nsew", padx=1)
            self._btns.append(btn)

    # -- public API ---------------------------------------------------------

    def get(self) -> str:
        return self._values[self._selected_idx]

    def set(self, value: str) -> None:
        if value not in self._values:
            return
        self._selected_idx = self._values.index(value)
        for i, btn in enumerate(self._btns):
            if i == self._selected_idx:
                btn.configure(fg_color=self._sel_color,
                              hover_color=COLOR_ACCENT_LIGHT)
            else:
                btn.configure(fg_color=self._unsel_color,
                              hover_color=COLOR_GLASS_HOVER)

    def configure(self, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._disabled = state == "disabled"
            for btn in self._btns:
                btn.configure(state=state)
        if kwargs:
            super().configure(**kwargs)

    # -- internal -----------------------------------------------------------

    def _on_click(self, idx: int) -> None:
        if self._disabled or idx == self._selected_idx or self._animating:
            return
        old_idx = self._selected_idx
        self._selected_idx = idx
        self._animating = True
        self._crossfade(old_idx, idx, 0)

    def _crossfade(self, old_idx: int, new_idx: int, step: int) -> None:
        if step > self._ANIM_FRAMES:
            self._btns[old_idx].configure(
                fg_color=self._unsel_color, hover_color=COLOR_GLASS_HOVER,
            )
            self._btns[new_idx].configure(
                fg_color=self._sel_color, hover_color=COLOR_ACCENT_LIGHT,
            )
            self._animating = False
            return
        t = step / self._ANIM_FRAMES
        eased = 1 - (1 - t) ** 3  # cubic ease-out
        self._btns[old_idx].configure(
            fg_color=_lerp_hex(self._sel_color, self._unsel_color, eased),
        )
        self._btns[new_idx].configure(
            fg_color=_lerp_hex(self._unsel_color, self._sel_color, eased),
        )
        ms = max(1, self._ANIM_MS // self._ANIM_FRAMES)
        self.after(ms, lambda: self._crossfade(old_idx, new_idx, step + 1))


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
        self._progress_value = 0.0
        self._progress_anim_id: str | None = None
        self._status_anim_id: str | None = None
        self._preview_debounce_id: str | None = None
        self._last_previewed_url: str = ""

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
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        self.url_entry.bind("<KeyRelease>", self._on_url_changed)
        self.url_entry.bind("<<Paste>>", self._on_url_changed)

        # Preview card (hidden until a valid URL is detected)
        self._preview_frame = ctk.CTkFrame(
            card,
            fg_color=COLOR_GLASS_LIGHT,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        # Not gridded yet — will be shown/hidden dynamically

        self._preview_thumb = ctk.CTkLabel(
            self._preview_frame,
            text="",
            width=120,
            height=68,
            fg_color=COLOR_BG_PRIMARY,
            corner_radius=8,
        )
        self._preview_thumb.grid(row=0, column=0, rowspan=3, padx=(12, 12), pady=12, sticky="nsw")

        self._preview_title = ctk.CTkLabel(
            self._preview_frame,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
            wraplength=500,
        )
        self._preview_title.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 2))

        self._preview_meta = ctk.CTkLabel(
            self._preview_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        self._preview_meta.grid(row=1, column=1, sticky="ew", padx=(0, 12))

        self._preview_status = ctk.CTkLabel(
            self._preview_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        self._preview_status.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))

        self._preview_frame.grid_columnconfigure(1, weight=1)

        # Divider line
        divider1 = ctk.CTkFrame(card, fg_color=COLOR_BORDER, height=1)
        divider1.grid(row=3, column=0, sticky="ew", padx=20, pady=0)

        # Format and Folder Section
        options_frame = ctk.CTkFrame(card, fg_color="transparent")
        options_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=20)
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

        self.format_selector = AnimatedToggle(
            options_frame,
            values=["MP4 Video", "MP3 Audio"],
            height=34,
            font=ctk.CTkFont(size=11, weight="bold"),
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
        self.download_button.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 20))

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

    # -- animation helpers --------------------------------------------------

    @staticmethod
    def _lerp_color(c1: str, c2: str, t: float) -> str:
        return _lerp_hex(c1, c2, t)

    def _animate_progress(self, target: float) -> None:
        """Smoothly interpolate the progress bar to *target*."""
        if self._progress_anim_id:
            self.after_cancel(self._progress_anim_id)
            self._progress_anim_id = None
        target = max(0.0, min(1.0, target))
        self._progress_step(self._progress_value, target, 0, 5)

    def _progress_step(self, start: float, end: float, step: int, total: int) -> None:
        if step > total:
            self.progress.set(end)
            self._progress_value = end
            self._progress_anim_id = None
            return
        t = step / total
        eased = 1 - (1 - t) ** 2  # quadratic ease-out
        val = start + (end - start) * eased
        self.progress.set(val)
        self._progress_value = val
        self._progress_anim_id = self.after(
            16, lambda: self._progress_step(start, end, step + 1, total),
        )

    def _set_status_animated(self, text: str, target_color: str) -> None:
        """Set status text with a colour fade-in."""
        self.status_line.configure(text=text)
        if self._status_anim_id:
            self.after_cancel(self._status_anim_id)
        self._status_fade(COLOR_BG_SECONDARY, target_color, 0, 8)

    def _status_fade(self, c_from: str, c_to: str, step: int, total: int) -> None:
        if step > total:
            self.status_line.configure(text_color=c_to)
            self._status_anim_id = None
            return
        t = step / total
        eased = 1 - (1 - t) ** 2
        self.status_line.configure(text_color=self._lerp_color(c_from, c_to, eased))
        self._status_anim_id = self.after(
            25, lambda: self._status_fade(c_from, c_to, step + 1, total),
        )

    # -- path helpers -------------------------------------------------------

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

    def _on_url_changed(self, event=None) -> None:
        """Debounce URL changes and trigger preview fetch."""
        if self._preview_debounce_id:
            self.after_cancel(self._preview_debounce_id)
        self._preview_debounce_id = self.after(600, self._trigger_preview)

    def _trigger_preview(self) -> None:
        """Start a background fetch for video info if URL changed."""
        url = self.url_entry.get().strip()
        if not url or url == self._last_previewed_url:
            if not url:
                self._hide_preview()
            return
        self._last_previewed_url = url
        self._show_preview_loading()
        threading.Thread(target=self._fetch_preview, args=(url,), daemon=True).start()

    def _fetch_preview(self, url: str) -> None:
        """Background: fetch video info and thumbnail, then update UI."""
        try:
            info = fetch_video_info(url)
            # Fetch thumbnail image bytes
            thumb_image = None
            if info.thumbnail_url:
                try:
                    req = urllib.request.Request(
                        info.thumbnail_url,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                    pil_img = Image.open(io.BytesIO(data))
                    # Crop to 16:9 if needed
                    w, h = pil_img.size
                    target_ratio = 16 / 9
                    if abs(w / h - target_ratio) > 0.1:
                        new_h = int(w / target_ratio)
                        if new_h <= h:
                            top = (h - new_h) // 2
                            pil_img = pil_img.crop((0, top, w, top + new_h))
                    pil_img = pil_img.resize((120, 68), Image.LANCZOS)
                    thumb_image = ctk.CTkImage(pil_img, size=(120, 68))
                except Exception:
                    thumb_image = None
            # Schedule UI update on main thread
            self.after(0, lambda: self._update_preview(info, thumb_image, url))
        except Exception as e:
            self.after(0, lambda: self._show_preview_error(url))

    def _show_preview_loading(self) -> None:
        """Show preview card with loading state."""
        self._preview_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        self._preview_thumb.configure(image=None, text="⏳")
        self._preview_title.configure(text="Fetching video info…")
        self._preview_meta.configure(text="")
        self._preview_status.configure(text="")

    def _update_preview(self, info: VideoInfo, thumb_image, url: str) -> None:
        """Update preview card with fetched info."""
        # Only update if URL hasn't changed since we started
        if self.url_entry.get().strip() != url:
            return
        if thumb_image:
            self._preview_thumb.configure(image=thumb_image, text="")
        else:
            self._preview_thumb.configure(image=None, text="🎬")
        self._preview_title.configure(text=info.title)
        mins, secs = divmod(info.duration, 60)
        hrs, mins = divmod(mins, 60)
        if hrs:
            dur_str = f"{hrs}:{mins:02d}:{secs:02d}"
        else:
            dur_str = f"{mins}:{secs:02d}"
        self._preview_meta.configure(text=f"{info.channel}  •  {dur_str}")
        self._preview_status.configure(text="✓ Video found", text_color=COLOR_SUCCESS)

    def _show_preview_error(self, url: str) -> None:
        """Show error state in preview card."""
        if self.url_entry.get().strip() != url:
            return
        self._preview_thumb.configure(image=None, text="✗")
        self._preview_title.configure(text="Could not load video info")
        self._preview_meta.configure(text="Check the URL and try again")
        self._preview_status.configure(text="", text_color=COLOR_ERROR)

    def _hide_preview(self) -> None:
        """Hide the preview card."""
        self._preview_frame.grid_remove()
        self._last_previewed_url = ""

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

        self._progress_value = 0.0
        self.progress.set(0.0)
        self._set_status_animated("Starting download…", COLOR_TEXT_SECONDARY)
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
                    self._animate_progress(value)
                    self.status_line.configure(text=format_status_line(evt), text_color=COLOR_TEXT_SECONDARY)
                elif et == "done":
                    ok = bool(evt.get("ok", False))
                    self._set_busy(False)
                    if ok:
                        self._animate_progress(1.0)
                        self._set_status_animated("✓ Download complete!", COLOR_SUCCESS)
                        self._log("✓ Download complete!")
                        # Capture download for history
                        self._capture_download_history()
                    else:
                        self._set_status_animated("✗ Download failed. Check log.", COLOR_ERROR)
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
