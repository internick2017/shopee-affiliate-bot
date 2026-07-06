@echo off
title Bot de ofertas (Amazon + Shopee -^> canal Lanny)
cd /d "E:\dev\07-tools-personal\shopee-affiliate-bot"
echo ============================================
echo   Bot de ofertas - escucha los grupos y postea al canal de Lanny
echo   (Amazon con tu tag; Shopee reenviado a revisar)
echo   (Ctrl+C para detener)
echo ============================================
python run_ofertas.py
echo.
echo El bot se detuvo. Revisa los mensajes de arriba.
pause
