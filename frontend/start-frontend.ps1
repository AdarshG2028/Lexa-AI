param(
    [int]$Port = 8080,
    [string]$Api = "http://localhost:8001"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Fail($message) {
    Write-Host "x $message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Fail "bun is not on PATH. Install it from https://bun.sh"
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    bun install
    if ($LASTEXITCODE -ne 0) { Fail "bun install failed." }
}

$holder = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($holder) {
    $name = (Get-Process -Id $holder[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Fail "Port $Port is already in use by '$name' (PID $($holder[0].OwningProcess)). Pass -Port 8081 (8080, 8081 and 5173 are allowed by the backend's CORS)."
}

try {
    Invoke-WebRequest -Uri "$Api/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "Backend reachable at $Api" -ForegroundColor Green
} catch {
    Write-Host "! Backend not answering at $Api. Start scripts\start-backend.ps1 first, or the app will show connection errors." -ForegroundColor Yellow
}

$env:VITE_API_BASE_URL = $Api

Write-Host "Frontend -> http://localhost:$Port" -ForegroundColor Green
Write-Host "Ctrl+C to stop.`n"

bun run dev --port $Port --strictPort
