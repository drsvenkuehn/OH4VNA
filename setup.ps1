# OH4VNA Quick Setup Script for Windows
# Run this script to quickly set up the OH4VNA development environment

Write-Host "Setting up OH4VNA development environment..." -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "app.py")) {
    Write-Host "ERROR: Please run this script from the OH4VNA project root directory" -ForegroundColor Red
    Write-Host "Expected to find app.py in current directory" -ForegroundColor Red
    exit 1
}

# Check for Python 3.11
Write-Host "Checking for Python 3.11..." -ForegroundColor Yellow
$pythonVersion = py -3.11 --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python 3.11 not found" -ForegroundColor Red
    Write-Host "Installing Python 3.11 via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.11
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install Python 3.11" -ForegroundColor Red
        exit 1
    }
}

# Create virtual environment
Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    py -3.11 -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "INFO: Virtual environment already exists" -ForegroundColor Cyan
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& ".\venv\Scripts\pip.exe" install -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed successfully" -ForegroundColor Green

# Copy configuration template
Write-Host "Setting up configuration..." -ForegroundColor Yellow
if (-not (Test-Path "configs\settings.yaml")) {
    Copy-Item "configs\settings.example.yaml" "configs\settings.yaml"
    Write-Host "Created configs\settings.yaml from template" -ForegroundColor Green
} else {
    Write-Host "INFO: configs\settings.yaml already exists" -ForegroundColor Cyan
}

# Test the application
Write-Host "Testing application startup..." -ForegroundColor Yellow
$job = Start-Job -ScriptBlock {
    param($venvPath)
    & "$venvPath\Scripts\streamlit.exe" run app.py --server.headless true --server.port 8503
} -ArgumentList (Resolve-Path ".\venv")

Start-Sleep -Seconds 10
$job | Stop-Job
$job | Remove-Job

if ($job.State -eq "Running") {
    Write-Host "Application startup test successful" -ForegroundColor Green
} else {
    Write-Host "WARNING: Application startup test had issues, but this might be normal" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete! Your OH4VNA development environment is ready." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Activate the environment: .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "2. Run the application: streamlit run app.py" -ForegroundColor White
Write-Host "3. Open your browser to: http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "Important files to review:" -ForegroundColor Cyan
Write-Host "• README.md - Project overview and usage" -ForegroundColor White
Write-Host "• .github\copilot-context.md - Complete development history" -ForegroundColor White
Write-Host "• .github\copilot-instructions.md - Copilot guidelines" -ForegroundColor White
Write-Host "• TRANSFER_GUIDE.md - Detailed setup instructions" -ForegroundColor White
Write-Host ""
Write-Host "The application implements Z43 design system with official corporate colors" -ForegroundColor Magenta
Write-Host "Includes simulation mode for development without VNA hardware" -ForegroundColor Magenta
Write-Host "Professional VNA workflow: Calibration -> Measurement -> Analysis" -ForegroundColor Magenta