Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Building HR Payslip Automator Binary   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Clean previous build artifacts
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# 2. Run PyInstaller
& ".\venv\Scripts\pyinstaller.exe" --noconfirm HRPayslipAutomator.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] PyInstaller build completed!" -ForegroundColor Green
    Write-Host "Standalone binary located at: dist\HRPayslipAutomator\HRPayslipAutomator.exe" -ForegroundColor Yellow
    Write-Host ""
    
    # Check if Inno Setup compiler is installed
    $isccPath = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if (-not $isccPath) {
        $defaultInnoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        if (Test-Path $defaultInnoPath) {
            $isccPath = $defaultInnoPath
        }
    }

    if ($isccPath) {
        Write-Host "Compiling Inno Setup Installer..." -ForegroundColor Cyan
        & $isccPath "installer.iss"
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[SUCCESS] Windows Setup Installer created!" -ForegroundColor Green
            Write-Host "Installer: dist_installer\HRPayslipAutomator_Setup_v1.0.0.exe" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[INFO] Inno Setup (iscc.exe) not found on PATH." -ForegroundColor DarkYellow
        Write-Host "To generate the one-click Setup .exe, install Inno Setup (https://jrsoftware.org/isdl.php) and compile 'installer.iss'." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "[ERROR] PyInstaller build failed." -ForegroundColor Red
}
