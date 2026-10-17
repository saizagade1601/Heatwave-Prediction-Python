@echo off
REM Stops the HeatGuard AI server that runs in the background.
REM (You can also click "Stop server" in the dashboard sidebar.)
curl -s -X POST http://localhost:5000/api/shutdown >nul 2>nul
echo HeatGuard AI server stopped. You can close the browser tab.
timeout /t 2 >nul
