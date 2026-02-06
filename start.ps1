# MsgSkill Windows Startup Script
# Start scheduler and preview server

$ErrorActionPreference = "Continue"

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "MsgSkill - AI Information Aggregator" -ForegroundColor Cyan
Write-Host "================================================"
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python not found!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "OK: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found! Please install Python 3.10+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow
python -c "import flask" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "OK: Dependencies installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting services" -ForegroundColor Cyan
Write-Host "================================================"
Write-Host ""

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
    Write-Host "Created logs directory" -ForegroundColor Green
}

# Check files
if (-not (Test-Path "src\msgskill\multi_scheduler.py")) {
    Write-Host "ERROR: multi_scheduler.py not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path "src\msgskill\preview_server.py")) {
    Write-Host "ERROR: preview_server.py not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start scheduler in new window
Write-Host "Starting scheduler in new window..." -ForegroundColor Green
try {
    $schedulerProcess = Start-Process -FilePath "python" `
        -ArgumentList "src\msgskill\multi_scheduler.py" `
        -WindowStyle Normal `
        -WorkingDirectory $scriptDir `
        -PassThru `
        -ErrorAction Stop
    
    Write-Host "OK: Scheduler started (PID: $($schedulerProcess.Id))" -ForegroundColor Green
    Write-Host "Log file: logs\scheduler.log" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Failed to start scheduler: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Wait for scheduler to start
Start-Sleep -Seconds 2

# Start preview server
Write-Host ""
Write-Host "Starting preview server..." -ForegroundColor Green
Write-Host "Access URL: http://localhost:5001" -ForegroundColor Cyan
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop preview server" -ForegroundColor Yellow
Write-Host "Close scheduler window to stop scheduler" -ForegroundColor Yellow
Write-Host "================================================"
Write-Host ""

# Run preview server
try {
    python src\msgskill\preview_server.py
} catch {
    Write-Host ""
    Write-Host "Preview server error: $_" -ForegroundColor Red
} finally {
    Write-Host ""
    Write-Host "Stopping services..." -ForegroundColor Yellow
    if ($schedulerProcess -and !$schedulerProcess.HasExited) {
        try {
            Stop-Process -Id $schedulerProcess.Id -Force -ErrorAction SilentlyContinue
            Write-Host "Scheduler stopped" -ForegroundColor Green
        } catch {
            Write-Host "Note: Please close scheduler window manually" -ForegroundColor Yellow
        }
    }
    Write-Host "Preview server stopped" -ForegroundColor Green
}
