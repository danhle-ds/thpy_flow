@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: run.bat — Shortcut chạy api_weight pipeline
:: Dùng để đăng ký trong Windows Task Scheduler
::
:: Usage:
::   run.bat              → production (mặc định)
::   run.bat dev          → dev mode
::   run.bat dry_run      → dry run (không ghi file, không gửi)
:: ─────────────────────────────────────────────────────────────────────────────

set "PROJECT_DIR=D:\PYTHON_TOOLS\project\info_herd\api_weight"
set "PYTHON=python"

:: Set RUN_MODE từ argument (mặc định: production)
if "%1"=="" (set "RUN_MODE=production") else (set "RUN_MODE=%1")

echo.
echo [api_weight] RUN_MODE=%RUN_MODE%
echo.

cd /d "%PROJECT_DIR%"
set RUN_MODE=%RUN_MODE%
%PYTHON% main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [api_weight] FAILED with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo [api_weight] DONE
