@echo off
rem Diagnostic run: writes UserData\diag\run_log.txt for bug reports.
rem For a full log, patch with:  Patch.bat -DebugLog
cd /d "%~dp0"
if not exist "UserData\diag" mkdir "UserData\diag"
set A6_WATCHDOG=1
set A6_DUMP_UNRESOLVED=1
set A6_WINDOWED=1
echo Running Asphalt 6 with diagnostics (windowed)...
echo If it hangs, wait about a minute, then close the game.
"Asphalt 6.exe" > "UserData\diag\run_log.txt" 2>&1
echo.
echo Log saved to UserData\diag\run_log.txt
pause
