# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

# PyInstaller executes the spec via exec(); __file__ may not be defined.
# SPECPATH is provided by PyInstaller and points to the spec directory.
ROOT = Path(SPECPATH).resolve().parent
APP = ROOT / "app" / "main.py"
ASSETS_FFMPEG = ROOT / "assets" / "ffmpeg"

datas = []
if ASSETS_FFMPEG.exists():
    # Bundle the entire folder so yt-dlp can find ffmpeg.exe and ffprobe.exe via ffmpeg_location.
    datas.append((str(ASSETS_FFMPEG), str(Path("assets") / "ffmpeg")))

a = Analysis(
    [str(APP)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["customtkinter", "yt_dlp"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="YTTF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="YTTF",
)
