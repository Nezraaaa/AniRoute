# AniRoute one-command start (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File scripts/start.ps1
# First run: creates .venv, installs CPU PyTorch + backend packages and frontend packages.
# Then starts the API on http://127.0.0.1:8000 and the web app on http://127.0.0.1:5173.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Creating Python virtual environment (.venv)...'
    py -3.12 -m venv .venv 2>$null
    if (-not (Test-Path $python)) { python -m venv .venv }
}

& $python -c "import ultralytics, cv2, fastapi, multipart" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing backend packages (first run downloads about 300 MB)...'
    & $python -m pip install --upgrade pip
    & $python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
    & $python -m pip install -r backend/requirements.txt
}

if (-not (Test-Path 'frontend\node_modules')) {
    Write-Host 'Installing frontend packages...'
    Push-Location frontend
    npm ci
    Pop-Location
}
if (-not (Test-Path 'frontend\.env')) { Copy-Item 'frontend\.env.example' 'frontend\.env' }

Write-Host 'Starting API on http://127.0.0.1:8000 ...'
$api = Start-Process -FilePath $python -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000' -PassThru -WorkingDirectory $root
Write-Host 'Starting web app on http://127.0.0.1:5173 ...'
$web = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev', '--', '--port', '5173' -PassThru -WorkingDirectory (Join-Path $root 'frontend')

Start-Sleep -Seconds 4
Start-Process 'http://127.0.0.1:5173/'
Write-Host ''
Write-Host 'AniRoute is running. Close this window or press Ctrl+C to stop both servers.'
try {
    Wait-Process -Id $api.Id
} finally {
    foreach ($process in @($api, $web)) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
}
