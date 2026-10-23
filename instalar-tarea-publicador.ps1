<#
Crea (o actualiza) la tarea programada que publica en Shopee Video desde el celular.

Por que existe: Nick se olvidaba de subir los videos ya producidos. Esta tarea de
Windows (local, nada en la nube ni en la cuenta de Claude) corre
scripts\publicar_video.py --postar a varias horas del dia: cada corrida publica UN
video, el siguiente pendiente de su canal, y lo marca en grabados.db y en el panel.

Por que va aparte de instalar-tareas.ps1: re-registrar aquellas tareas reinicia los
bots que estan corriendo. Esta no tiene nada que ver con ellos.

Decisiones:
  - Un video por corrida, a horas separadas, con un retraso al azar de hasta 30
    minutos: ritmo de persona. Publicar en rafaga es lo que mas parece un robot.
  - Sin StartWhenAvailable: si la PC estaba apagada a la hora, esa publicacion se
    saltea. Recuperarlas todas juntas al prender seria justo la rafaga a evitar.
  - ExecutionTimeLimit 20 minutos: una publicacion tarda unos 2. Si la app se cuelga,
    Windows la corta y la proxima arranca limpia.
  - Si el celular no esta conectado o esta bloqueado, el script aborta sin publicar
    y lo deja escrito en logs\publicador.log.

Uso:
    powershell -ExecutionPolicy Bypass -File instalar-tarea-publicador.ps1
    powershell -ExecutionPolicy Bypass -File instalar-tarea-publicador.ps1 -Horas 9,13,17,21
    powershell -ExecutionPolicy Bypass -File instalar-tarea-publicador.ps1 -Desinstalar
#>

param(
    [switch]$Desinstalar,
    # Una publicacion por hora de la lista: 5 horas = 5 videos por dia.
    [int[]]$Horas = @(9, 12, 15, 18, 21)
)

$ErrorActionPreference = "Stop"
$nombre = "ShopeePublicarVideo"
$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Definition

if (Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Host "Borrada la version anterior de $nombre"
}
if ($Desinstalar) {
    Write-Host "Listo. Ya no se publica solo."
    return
}

# pythonw.exe (sin ventana negra) al lado del python.exe del PATH.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No encuentro python.exe en el PATH." }
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No encuentro pythonw.exe junto a $python" }

$accion = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "scripts\publicar_video.py --postar" -WorkingDirectory $proyecto
$disparadores = foreach ($h in $Horas) {
    New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($h)) `
        -RandomDelay (New-TimeSpan -Minutes 30)
}
$opciones = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparadores `
    -Settings $opciones -Principal $principal `
    -Description "Publica un video pendiente en Shopee Video desde el celular" | Out-Null

Write-Host "Creada: $nombre, a las $($Horas -join ', ') h (+ hasta 30 min al azar)."
Write-Host "Para probarla AHORA:  Start-ScheduledTask -TaskName $nombre"
Write-Host "Registro:             $proyecto\logs\publicador.log"
