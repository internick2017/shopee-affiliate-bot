@echo off
title Bajar mensajes de Telegram
cd /d "E:\dev\07-tools-personal\shopee-affiliate-bot"
echo ============================================
echo   Bajar mensajes de un canal de Telegram
echo   Canal por defecto: Crowman  ^|  40 mensajes
echo   La primera vez pide telefono + codigo.
echo ============================================
python fetch_mensajes.py Crowman 40
echo.
pause
