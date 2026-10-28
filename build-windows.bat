@echo off
rem Build the WANICNSURVEY installer (see build-windows.ps1 for what it needs)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-windows.ps1" %*
pause
