@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD="
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.13"
if defined PYTHON_CMD goto python_found
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if defined PYTHON_CMD goto python_found
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.11"
if defined PYTHON_CMD goto python_found
echo ERROR: Install Python 3.11, 3.12, or 3.13 (64-bit).
py -0p
pause
exit /b 1
:python_found
echo Using %PYTHON_CMD%
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto fail
if exist ge.ico goto icon_ready
%PYTHON_CMD% prepare_icon.py
if errorlevel 1 goto fail
:icon_ready
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name GE_Event --icon ge.ico --add-data "ge.ico;." main.py
if errorlevel 1 goto fail
%PYTHON_CMD% -c "import os; os.replace('dist/GE_Event.exe', 'dist/' + ''.join(map(chr,[71,69,32,51060,48292,53944])) + '.exe')"
if errorlevel 1 goto fail
echo SUCCESS. Check the dist folder.
pause
exit /b 0
:fail
echo Build failed. Read the error messages above.
pause
exit /b 1
