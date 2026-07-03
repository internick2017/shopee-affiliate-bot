@echo off
title Shopee Bot - Observar grupos
cd /d "E:\dev\07-tools-personal\shopee-affiliate-bot"
echo ============================================
echo   Modo OBSERVAR - descubrir grupos
echo   Muestra cada mensaje con su chat_id.
echo   (Ctrl+C para detener)
echo ============================================
python run.py --observe
echo.
echo Se detuvo. Revisa los mensajes de arriba.
pause
