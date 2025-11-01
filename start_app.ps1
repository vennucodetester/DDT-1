# PowerShell launcher script for HVAC System Analyzer
# Automatically creates logs directory and redirects output to dated log file

param(
    [string]$LogDir = "logs"
)

$ErrorActionPreference = "Stop"

# Get project directory (where this script is located)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ScriptDir

# Create logs directory if it doesn't exist
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "Created logs directory: $LogDir"
}

# Optional: Activate virtual environment if it exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..."
    . .\venv\Scripts\Activate.ps1
}

# Generate timestamp for log file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogDir "app_$timestamp.log"

Write-Host "Starting application..."
Write-Host "Log file: $logFile"
Write-Host ""

# Run application with logging
# Both stdout and stderr are captured and written to log file
python app.py --log $logFile 2>&1 | Tee-Object -FilePath $logFile


