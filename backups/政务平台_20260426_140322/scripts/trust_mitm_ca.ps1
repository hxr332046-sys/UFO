# Import mitmproxy CA into CurrentUser trusted roots (no admin). Run once per Windows user.
$ErrorActionPreference = "Stop"
$cer = Join-Path $env:USERPROFILE ".mitmproxy\mitmproxy-ca-cert.cer"
if (-not (Test-Path $cer)) {
    Write-Error "Missing $cer — start mitmdump once to generate certs."
}
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Write-Host "OK: mitm CA imported to CurrentUser\Root"
