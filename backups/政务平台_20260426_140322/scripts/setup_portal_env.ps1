# Portal env: Python 3.11 venv + requirements-portal.txt + dirs
# Run: cd G:\UFO\政务平台 ; .\scripts\setup_portal_env.ps1
$ErrorActionPreference = "Stop"
$PortalRoot = Split-Path -Parent $PSScriptRoot
Set-Location $PortalRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Error "Python launcher 'py' not found. Install Python 3.11."
}

$venv = Join-Path $PortalRoot ".venv-portal"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating venv (py -3.11): $venv"
    py -3.11 -m venv $venv
} else {
    Write-Host "Venv exists: $venv"
}

& $venvPy -m pip install -U pip
& (Join-Path $venv "Scripts\pip.exe") install -r (Join-Path $PortalRoot "requirements-portal.txt")

$udd = "C:\Temp\ChromeDevCDP"
if (-not (Test-Path $udd)) {
    New-Item -ItemType Directory -Path $udd -Force | Out-Null
    Write-Host "Created: $udd"
}

$rec = Join-Path $PortalRoot "dashboard\data\records"
if (-not (Test-Path $rec)) {
    New-Item -ItemType Directory -Path $rec -Force | Out-Null
}

Write-Host "OK. Next: .\scripts\start_chrome_dev_cdp.ps1  then  .\scripts\run_mitm_capture.ps1" -ForegroundColor Green
