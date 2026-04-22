$ErrorActionPreference = "Stop"
$PortalRoot = Split-Path -Parent $PSScriptRoot
Set-Location $PortalRoot

$cfgPath = Join-Path $PortalRoot "config\browser.json"
$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cdpPort = [int]$cfg.cdp_port
$cdpJson = "http://127.0.0.1:$cdpPort/json"

try {
    $null = Invoke-WebRequest -Uri $cdpJson -TimeoutSec 2 -UseBasicParsing
    Write-Host "CDP already up: $cdpJson"
    exit 0
} catch {
}

$venvPy = Join-Path $PortalRoot ".venv-portal\Scripts\python.exe"
$launcher = Join-Path $PortalRoot "scripts\launch_browser.py"
if (Test-Path $venvPy) {
    & $venvPy $launcher --no-proxy
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "WARN: .venv-portal missing; run setup_portal_env.ps1. Using system python."
    & python $launcher --no-proxy
} else {
    Write-Error "No Python. Run .\scripts\setup_portal_env.ps1"
}
exit $LASTEXITCODE
