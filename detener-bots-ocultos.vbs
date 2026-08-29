' Detiene los dos bots, corran como sea que hayan arrancado.
'
' OJO, esto es lo que mas confunde: desde que los bots corren como TAREAS
' PROGRAMADAS (ver instalar-tareas.ps1), matar el proceso desde el Administrador
' de tareas NO alcanza, Windows lo revive solo al minuto siguiente. Hay que
' terminar la tarea, que es lo que hace este script.
'
' Tambien mata las ventanas viejas lanzadas por los .vbs de iniciar, por si
' quedo alguna dando vueltas de antes.
'
' Para que dejen de arrancar solos al iniciar sesion:
'     powershell -ExecutionPolicy Bypass -File instalar-tareas.ps1 -Desinstalar

Set WshShell = CreateObject("WScript.Shell")
Set wmi = GetObject("winmgmts:\\.\root\cimv2")

tareas = Array("ShopeeBotOfertas", "ShopeeBotGenerador")
titulos = Array("BotOfertasLanny", "BotGeneradorPosts")
detenidos = ""

' 1) Terminar las tareas programadas (esto si frena el reinicio automatico).
For Each tarea In tareas
    If WshShell.Run("schtasks /End /TN " & tarea, 0, True) = 0 Then
        detenidos = detenidos & tarea & " (tarea programada)" & vbCrLf
    End If
Next

' 2) Matar las ventanas viejas de los lanzadores .vbs, si quedo alguna.
For Each titulo In titulos
    Set procesos = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name = 'cmd.exe'")
    For Each p In procesos
        If Not IsNull(p.CommandLine) Then
            If InStr(p.CommandLine, "title " & titulo) > 0 Then
                WshShell.Run "taskkill /F /T /PID " & p.ProcessId, 0, True
                detenidos = detenidos & titulo & " (lanzador viejo)" & vbCrLf
            End If
        End If
    Next
Next

If detenidos = "" Then
    WshShell.Popup "No habia ningun bot corriendo.", 6, "Detener Bots", 48
Else
    WshShell.Popup "Detenidos:" & vbCrLf & vbCrLf & detenidos & vbCrLf & _
        "Para volver a arrancarlos, usa el acceso directo de iniciar" & vbCrLf & _
        "o reinicia la sesion de Windows.", 10, "Detener Bots", 64
End If
