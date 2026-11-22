@echo off
cd /d "%~dp0"
set "RULE=rules\pipl-separate-consent_v2.5.yaml"
if not exist "%RULE%" (
  echo ’“≤ªµΩ %RULE%
  pause
  exit /b 1
)
start "" notepad "%RULE%"
