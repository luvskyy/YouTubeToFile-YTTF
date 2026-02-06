Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section($text) {
  Write-Host ""
  Write-Host "== $text =="
}

function Ensure-Venv {
  if (-not (Test-Path ".\.venv")) {
    Write-Section "Creating venv"
    python -m venv .venv
  }
  .\.venv\Scripts\python.exe -m pip install -U pip | Out-Null
}

function Install-Deps {
  Write-Section "Installing dependencies"
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

function Ensure-FFmpeg {
  Write-Section "Ensuring FFmpeg is present"
  $ffDir = Join-Path $PSScriptRoot "..\assets\ffmpeg"
  $ffDir = (Resolve-Path $ffDir).Path
  $ffmpegExe = Join-Path $ffDir "ffmpeg.exe"
  $ffprobeExe = Join-Path $ffDir "ffprobe.exe"

  if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
    Write-Host "FFmpeg already present in assets\ffmpeg"
    return
  }

  throw "FFmpeg not found in assets\ffmpeg. Place ffmpeg.exe + ffprobe.exe there, then re-run build."
}

function Build-Exe {
  Write-Section "Building .exe (PyInstaller)"
  $spec = Join-Path $PSScriptRoot "yt_to_file.spec"
  .\.venv\Scripts\pyinstaller.exe $spec --noconfirm
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
  }

  # PyInstaller may leave an extra top-level EXE; keep the onedir output only.
  $extraExe = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "dist\YouTubeToFile.exe"
  if (Test-Path $extraExe) {
    Remove-Item -Force $extraExe
  }
}

function Build-Installer {
  Write-Section "Building installer (Inno Setup)"

  $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
  $iss = Join-Path $repoRoot "installer\YouTubeToFile.iss"
  if (-not (Test-Path $iss)) {
    Write-Host "No installer script found at: $iss"
    return
  }

  # Default Inno Setup location. If not installed, we skip with instructions.
  $iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
  if (-not (Test-Path $iscc)) {
    Write-Host "Inno Setup not found. Install it, then re-run this build."
    Write-Host "Expected: $iscc"
    Write-Host "Download: https://jrsoftware.org/isdl.php"
    return
  }

  & $iscc $iss
  if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
  }

  $setupExe = Join-Path $repoRoot "installer\Output\YouTubeToFile-Setup.exe"
  if (Test-Path $setupExe) {
    Write-Host "Installer created: $setupExe"
  } else {
    Write-Host "Installer build finished; output not found at expected path: $setupExe"
  }
}

Write-Section "YouTubeToFile build"
Ensure-Venv
Install-Deps
Ensure-FFmpeg
Build-Exe
Build-Installer

Write-Section "Done"
Write-Host "Output: dist\YouTubeToFile\YouTubeToFile.exe"
