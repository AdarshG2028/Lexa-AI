param(
    [ValidateSet("all", "backend", "frontend", "stop", "status")]
    [string]$Target = "all",
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 8080
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendScript = Join-Path $root "backend\scripts\start-backend.ps1"
$frontendScript = Join-Path $root "frontend\start-frontend.ps1"
$backendUrl = "http://localhost:$BackendPort"
$frontendUrl = "http://localhost:$FrontendPort"

function Get-Listener($port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Test-Url($url) {
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-Url($url, $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url $url) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# Only ever stops processes that belong to this repository, so an unrelated app
# that happens to sit on the same port is left alone.
function Stop-Ours($port, $label) {
    $listener = Get-Listener $port
    if (-not $listener) {
        Write-Host "  $label : not running (port $port free)"
        return
    }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if ($proc.CommandLine -and $proc.CommandLine.Contains($root)) {
        taskkill /PID $listener.OwningProcess /T /F | Out-Null
        Write-Host "  $label : stopped (port $port)" -ForegroundColor Green
    } else {
        Write-Host "  $label : port $port is held by another program ($($proc.Name)); left alone" -ForegroundColor Yellow
    }
}

function Show-Status {
    foreach ($item in @(
        @{ Label = "backend "; Port = $BackendPort; Url = "http://127.0.0.1:$BackendPort/health" },
        @{ Label = "frontend"; Port = $FrontendPort; Url = "http://localhost:$FrontendPort/" }
    )) {
        $up = (Get-Listener $item.Port) -and (Test-Url $item.Url)
        $state = if ($up) { "up" } else { "down" }
        $color = if ($up) { "Green" } else { "DarkGray" }
        Write-Host ("  {0} port {1,-5} {2}" -f $item.Label, $item.Port, $state) -ForegroundColor $color
    }
}

switch ($Target) {
    "backend" {
        & $backendScript -Port $BackendPort
    }
    "frontend" {
        & $frontendScript -Port $FrontendPort -Api $backendUrl
    }
    "status" {
        Show-Status
    }
    "stop" {
        Write-Host "Stopping Lexa:"
        Stop-Ours $BackendPort "backend "
        Stop-Ours $FrontendPort "frontend"
    }
    "all" {
        foreach ($service in @(
            @{ Name = "backend"; Port = $BackendPort },
            @{ Name = "frontend"; Port = $FrontendPort }
        )) {
            if (Get-Listener $service.Port) {
                Write-Host "x Port $($service.Port) is already in use, so the $($service.Name) cannot start." -ForegroundColor Red
                Write-Host "  Run '.\dev.ps1 status' to see what is running, or '.\dev.ps1 stop' to stop it." -ForegroundColor Red
                exit 1
            }
        }

        # Each service gets its own window so their logs stay readable and
        # closing a window stops only that service.
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", "`$Host.UI.RawUI.WindowTitle = 'Lexa backend'; & '$backendScript' -Port $BackendPort"
        )
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", "`$Host.UI.RawUI.WindowTitle = 'Lexa frontend'; & '$frontendScript' -Port $FrontendPort -Api $backendUrl"
        )

        Write-Host "Starting Lexa..." -ForegroundColor Cyan
        $backendUp = Wait-Url "http://127.0.0.1:$BackendPort/health" 60
        $frontendUp = Wait-Url "$frontendUrl/" 120

        Write-Host ""
        Write-Host ("  backend   {0}   {1}" -f $backendUrl, $(if ($backendUp) { "ready" } else { "NOT RESPONDING - check its window" })) -ForegroundColor $(if ($backendUp) { "Green" } else { "Red" })
        Write-Host ("  frontend  {0}   {1}" -f $frontendUrl, $(if ($frontendUp) { "ready" } else { "NOT RESPONDING - check its window" })) -ForegroundColor $(if ($frontendUp) { "Green" } else { "Red" })
        Write-Host ""
        Write-Host "  API docs  $backendUrl/docs"
        Write-Host "  Stop both with: .\dev.ps1 stop"
    }
}
