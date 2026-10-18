@echo off
title TATA POWER DDL - Feeder GIS & SLD Portal (Zone 515 & 518)
cd /d "%~dp0web_gis"
echo ==============================================================================
echo           TATA POWER DELHI DISTRIBUTION LIMITED (ZONE 515 & 518)
echo             Enterprise Feeder GIS & Single Line Diagram (SLD) Portal
echo ==============================================================================
echo [INFO] Starting Local Portal Server on http://127.0.0.1:8000 ...
echo [INFO] Close this command window to stop the server.
echo.
start "" "http://127.0.0.1:8000"
python -m uvicorn server:app --host 127.0.0.1 --port 8000
pause
