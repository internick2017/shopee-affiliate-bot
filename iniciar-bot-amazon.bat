@echo off
title Bot Amazon (ofertas -> canal Lanny)
cd /d "E:\dev\07-tools-personal\shopee-affiliate-bot"
echo ============================================
echo   Bot Amazon - escucha el canal y postea
echo   ofertas de Amazon con tu tag al canal de Lanny
echo   (Ctrl+C para detener)
echo ============================================
python run_amazon.py
echo.
echo El bot se detuvo. Revisa los mensajes de arriba.
pause
