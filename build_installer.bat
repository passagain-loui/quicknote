@echo off
REM Build QuickNote Installer using Inno Setup
REM Requires Inno Setup 6.0+ to be installed

echo.
echo ========================================
echo QuickNote Installer Builder v2.9.41
echo ========================================
echo.

REM Try multiple Inno Setup paths
set ISCC_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    set ISCC_PATH=C:\Program Files (x86)\Inno Setup 5\ISCC.exe
) else (
    where iscc.exe >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Inno Setup is not installed or not in PATH
        echo.
        echo Please install Inno Setup from:
        echo https://jrsoftware.org/isdl.php
        echo.
        echo Tried paths:
        echo   - C:\Program Files (x86)\Inno Setup 6\ISCC.exe
        echo   - C:\Program Files\Inno Setup 6\ISCC.exe
        echo.
        echo After installation, try running this script again.
        echo.
        pause
        exit /b 1
    ) else (
        REM iscc.exe found in PATH
        for /f "delims=" %%a in ('where iscc.exe') do set ISCC_PATH=%%a
    )
)

echo [OK] Inno Setup compiler found at:
echo %ISCC_PATH%
echo.

REM Build the installer
echo Building installer...
"%ISCC_PATH%" installer.iss

if errorlevel 1 (
    echo.
    echo [ERROR] Installer build failed!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Installer built successfully!
echo ========================================
echo.
echo Output: installer_output\QuickNote_v2.9.41_Setup.exe
echo.
pause
