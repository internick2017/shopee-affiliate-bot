' Arranca los DOS bots (ofertas + generador de posts) en segundo plano,
' sin ninguna ventana visible. Equivalente oculto de iniciar-todo.bat.
'
' Simplemente lanza los dos .vbs individuales, que ya tienen su propia
' proteccion contra procesos duplicados.
'
' Para pararlos: Administrador de Tareas (busca python.exe con ventana
' titulada BotOfertasLanny o BotGeneradorPosts).

Set WshShell = CreateObject("WScript.Shell")
projectDir = "E:\dev\07-tools-personal\shopee-affiliate-bot"

WshShell.Run """" & projectDir & "\iniciar-bot-ofertas-oculto.vbs""", 0, False
WshShell.Run """" & projectDir & "\iniciar-bot-generador-oculto.vbs""", 0, False
