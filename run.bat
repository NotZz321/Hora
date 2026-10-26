@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo เปิดเว็บที่ http://127.0.0.1:5000  (ปิดหน้าต่างนี้เพื่อหยุด)
where python >nul 2>nul && (python app.py) || (py app.py)
pause
