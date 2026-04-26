# mitmdump + mitm_capture_ufo -> dashboard/data/records/mitm_ufo_flows.jsonl
# Proxy browser to 127.0.0.1:8080 ; install mitm CA
# Run: cd G:\UFO\政务平台 ; .\scripts\run_mitm_capture.ps1
$ErrorActionPreference = "Stop"
$PortalRoot = Split-Path -Parent $PSScriptRoot
Set-Location $PortalRoot

$Addon = Join-Path $PortalRoot "system\mitm_capture_ufo.py"
if (-not (Test-Path $Addon)) {
    Write-Error "Addon not found: $Addon"
}

$mitmdump = Join-Path $PortalRoot ".venv-portal\Scripts\mitmdump.exe"
if (-not (Test-Path $mitmdump)) {
    Write-Error "mitmdump not found. Run: .\scripts\setup_portal_env.ps1"
}

Write-Host "Out: dashboard\data\records\mitm_ufo_flows.jsonl"
Write-Host "Proxy: 127.0.0.1:8080"
& $mitmdump -s $Addon
