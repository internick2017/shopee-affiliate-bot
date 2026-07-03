@echo off
title Shopee Bot - Observar grupos
cd /d "%~dp0"
echo ============================================
echo   Modo OBSERVAR - descubrir grupos
echo   Muestra cada mensaje con su chat_id.
echo   Sirve para ver de que grupos escuchar y
echo   si postean links de Shopee.
echo   (Ctrl+C para detener)
echo ============================================
python run.py --observe
echo.
echo Se detuvo. Revisa los mensajes de arriba.
pause
