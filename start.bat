@echo off
cd /d "%~dp0"
cls
echo ============================================
echo    SilvaCare Activity Payment Portal
echo ============================================
echo.
echo Setting up admin user + demo data...
python seed_data.py
echo.
echo ============================================
echo   Public:    http://127.0.0.1:8000/
echo   Headoffice: http://127.0.0.1:8000/headoffice/
echo   Site Senior: http://127.0.0.1:8000/site/dashboard/
echo.
echo   Login as admin:    antony.blacker@silvacare.org.uk / changeme123
echo   Login as senior:   maplemanager / password123
echo ============================================
echo.
python manage.py runserver 127.0.0.1:8000
pause
