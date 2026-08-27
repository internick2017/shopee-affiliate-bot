' Arranca el Bot de ofertas (Amazon + Shopee -> canal Lanny) en segundo
' plano, sin ventana visible. Equivalente oculto de iniciar-bot-ofertas.bat.
'
' Si ya esta corriendo (por ejemplo, clickeaste el icono dos veces), NO
' vuelve a lanzarlo - te avisa y listo, para evitar procesos duplicados.
'
' Para pararlo: Administrador de Tareas (busca python.exe con ventana
' titulada BotOfertasLanny).

Set WshShell = CreateObject("WScript.Shell")
projectDir = "E:\dev\07-tools-personal\shopee-affiliate-bot"

Function YaEstaCorriendo(tituloVentana)
    Dim wmi, procesos, p
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    Set procesos = wmi.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE Name = 'cmd.exe'")
    YaEstaCorriendo = False
    For Each p In procesos
        If Not IsNull(p.CommandLine) Then
            If InStr(p.CommandLine, "title " & tituloVentana) > 0 Then
                YaEstaCorriendo = True
                Exit Function
            End If
        End If
    Next
End Function

If YaEstaCorriendo("BotOfertasLanny") Then
    WshShell.Popup "El Bot de Ofertas ya esta corriendo. No se lanzo nada nuevo.", 5, "Bot de Ofertas", 48
Else
    ' 0 = ventana oculta, False = no esperar a que termine
    WshShell.Run "cmd /c title BotOfertasLanny && cd /d """ & projectDir & """ && python run_ofertas.py", 0, False
    WshShell.Popup "Bot de Ofertas iniciado.", 4, "Bot de Ofertas", 64
End If
