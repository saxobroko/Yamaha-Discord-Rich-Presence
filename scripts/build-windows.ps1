# Build YamahaDiscordRPC.exe (one-file) on Windows.
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean YamahaDiscordRPC.spec

$exe = Join-Path "dist" "YamahaDiscordRPC.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}
Get-Item $exe | Format-List FullName, Length, LastWriteTime
Write-Host "Built: $exe"
