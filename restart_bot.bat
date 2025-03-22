@echo off
echo Restarting bot...
taskkill /F /IM python.exe
timeout /t 5
start python main.py
