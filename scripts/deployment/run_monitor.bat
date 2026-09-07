@echo off
rem Course Compass monitor worker (course seat monitoring + auto-enroll) - restart loop for Windows.
rem Registered in Task Scheduler as "Course_Compass_Monitor" (run at startup, S4U, no login needed).
rem Expects a venv at .venv\ and .env in the repo root. Writes logs\monitor.log (stdout) and
rem logs\ntust_monitor.log (application log, rotated daily by backend/monitor/utils.py).
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
if not exist logs mkdir logs
:loop
for %%F in (logs\monitor.log) do if %%~zF GTR 10485760 move /y logs\monitor.log logs\monitor.log.1 > nul
echo [%date% %time%] starting monitor worker >> logs\monitor.log
".venv\Scripts\python.exe" -m backend.monitor.worker >> logs\monitor.log 2>&1
echo [%date% %time%] monitor worker exited with code %errorlevel%, restarting in 30s >> logs\monitor.log
ping -n 31 127.0.0.1 > nul
goto loop
