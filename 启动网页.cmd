@echo off
setlocal
set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%code\.venv\Scripts\python.exe" (
    echo Python environment missing. Please follow code/README.md to install it.
    pause
    exit /b 1
)
"%PROJECT_DIR%code\.venv\Scripts\python.exe" "%PROJECT_DIR%code\web\server.py" --open-browser %*
if errorlevel 1 pause
endlocal
