@echo off
title Bajar mensajes de Telegram
cd /d "%~dp0"
echo ============================================
echo   Bajar mensajes de un canal de Telegram
echo   (para armar el extractor de nombres)
echo.
echo   Canal por defecto: Crowman  ^|  40 mensajes
echo   La primera vez pide telefono + codigo.
echo ============================================
python fetch_mensajes.py Crowman 40
echo.
pause
