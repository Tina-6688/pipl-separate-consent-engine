@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo === 1/2  validate.py  ===
python validate.py
set V1=%ERRORLEVEL%

echo.
echo === 2/2  test_validator.py  ===
python test_validator.py
set V2=%ERRORLEVEL%

echo.
if "%V1%%V2%"=="00" (
  echo RESULT: ALL PASS
) else (
  echo RESULT: FAILED  validate=%V1%  test_validator=%V2%
)
echo.
pause