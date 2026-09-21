param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Fail($message) {
    Write-Host "x $message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv is not on PATH. Install it from https://docs.astral.sh/uv/"
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Fail "ffmpeg is not on PATH. Every audio turn is converted with it."
}
if (-not (Test-Path ".env")) {
    Fail ".env is missing. Copy .env.example to .env and add GROQ_API_KEY."
}

$holder = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($holder) {
    $name = (Get-Process -Id $holder[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Fail "Port $Port is already in use by '$name' (PID $($holder[0].OwningProcess)). Pass -Port to use another."
}

$env:HF_HOME = Join-Path $root "data\models"
if (Test-Path $env:HF_HOME) {
    $env:HF_HUB_OFFLINE = "1"
}

Write-Host "Backend  -> http://localhost:$Port   (docs: /docs)" -ForegroundColor Green
Write-Host "Ctrl+C to stop.`n"

uv run uvicorn app.main:app --port $Port
