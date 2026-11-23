# AniRoute for a phone on the same Wi-Fi (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File scripts/start-lan.ps1
# Starts the API (on this laptop only) and the web app in LAN mode, which forwards the app's API calls
# to the API. The phone only needs port 5173. Run scripts/start.ps1 once first so packages are installed.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run scripts/start.ps1 once first (it installs the packages).' }

$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback' } |
    Select-Object -ExpandProperty IPAddress

$rule = Get-NetFirewallRule -DisplayName 'AniRoute web app (5173)' -ErrorAction SilentlyContinue
if (-not $rule) {
    Write-Host ''
    Write-Host 'One-time setup: allow phones to reach port 5173. In an *administrator* PowerShell, run:' -ForegroundColor Yellow
    Write-Host "  New-NetFirewallRule -DisplayName 'AniRoute web app (5173)' -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any" -ForegroundColor Yellow
    Write-Host ''
}

Write-Host 'Starting API on this laptop (127.0.0.1:8000) ...'
$api = Start-Process -FilePath $python -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000' -PassThru -WorkingDirectory $root
Write-Host 'Starting web app for the network (port 5173) ...'
$web = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'lan' -PassThru -WorkingDirectory (Join-Path $root 'frontend')

Start-Sleep -Seconds 4
Write-Host ''
Write-Host 'On your phone (same Wi-Fi), open:' -ForegroundColor Green
foreach ($ip in $ips) { Write-Host "  https://${ip}:5173" -ForegroundColor Green }
Write-Host ''
Write-Host 'First visit: the phone warns about the certificate. Accept it once (see docs/PHONE_ON_WIFI.md).'
Write-Host 'Press Ctrl+C or close this window to stop.'
try { Wait-Process -Id $api.Id, $web.Id } finally { Stop-Process -Id $api.Id, $web.Id -ErrorAction SilentlyContinue }
