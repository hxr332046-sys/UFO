# Start Chrome Dev with CDP 9225 (see config/browser.json)
# Run: cd G:\UFO\政务平台 ; .\scripts\start_chrome_dev_cdp.ps1
$ErrorActionPreference = "Stop"
$PortalRoot = Split-Path -Parent $PSScriptRoot
Set-Location $PortalRoot

try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:9225/json" -TimeoutSec 2 -UseBasicParsing
    Write-Host "CDP already up: http://127.0.0.1:9225/json"
    exit 0
} catch {
}

$venvPy = Join-Path $PortalRoot ".venv-portal\Scripts\python.exe"
$launcher = Join-Path $PortalRoot "scripts\launch_browser.py"
if (Test-Path $venvPy) {
    & $venvPy $launcher
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "WARN: .venv-portal missing; run setup_portal_env.ps1. Using system python."
    & python $launcher
} else {
    Write-Error "No Python. Run .\scripts\setup_portal_env.ps1"
}
exit $LASTEXITCODE
