' Muestreo diario de ventas por producto: insumo del detector de tendencia
' (/tendencia en el bot generador).
'
' Corre run_snapshot.py sin ventana visible. Pensado para el Programador de
' tareas de Windows, una vez por dia. Tarda ~30 segundos (16 categorias con
' pausa entre llamadas por el rate limit de la API).
'
' Correrlo dos veces el mismo dia NO duplica datos: la clave de la tabla
' incluye el dia, asi que la segunda corrida pisa a la primera.

Set WshShell = CreateObject("WScript.Shell")
projectDir = "E:\dev\07-tools-personal\shopee-affiliate-bot"

WshShell.Run "cmd /c title MuestreoDiario && cd /d """ & projectDir & """ && python run_snapshot.py", 0, False
