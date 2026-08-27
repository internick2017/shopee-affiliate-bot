' Detiene los bots que fueron iniciados en modo oculto (iniciar-bot-ofertas-oculto.vbs,
' iniciar-bot-generador-oculto.vbs o iniciar-todo-oculto.vbs).
'
' Busca los procesos cmd.exe con el titulo BotOfertasLanny / BotGeneradorPosts y los
' mata junto con su proceso hijo (python.exe) usando taskkill /T.

Set WshShell = CreateObject("WScript.Shell")
Set wmi = GetObject("winmgmts:\\.\root\cimv2")

titulos = Array("BotOfertasLanny", "BotGeneradorPosts")
detenidos = ""

For Each titulo In titulos
    Set procesos = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name = 'cmd.exe'")
    For Each p In procesos
        If Not IsNull(p.CommandLine) Then
            If InStr(p.CommandLine, "title " & titulo) > 0 Then
                WshShell.Run "taskkill /F /T /PID " & p.ProcessId, 0, True
                detenidos = detenidos & titulo & vbCrLf
            End If
        End If
    Next
Next

If detenidos = "" Then
    WshShell.Popup "No se encontro ningun bot oculto corriendo.", 5, "Detener Bots", 48
Else
    WshShell.Popup "Bots detenidos:" & vbCrLf & detenidos, 5, "Detener Bots", 64
End If
