@echo off
rem Patch the Asphalt 6 Win32 port (fixes the hang on the Gameloft logo).
rem Add -DebugLog to also enable the diagnostic log, or -Restore to undo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch.ps1" %*
echo.
pause
