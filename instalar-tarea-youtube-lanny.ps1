<#
Crea (o actualiza) la tarea programada que sube los Shorts de Lanny a su canal de YouTube.

Corre scripts\youtube_lanny.py lote cada dia desde las 19:20: todos los videos nuevos
(menos de 2 dias) y 5 atrasados ya publicados en Shopee Video. YouTube corta al tope
diario del canal (~9 en octubre de 2026) y el lote frena solo en el primer rechazo.
No usa el celular: es todo por la API.

Decisiones:
  - Local, nunca en la nube (regla de Nick para sus tareas).
  - Reintentos cada 10 min durante 1 hora: el tope cuenta 24 horas corridas, y una hora
    fija caeria justo antes de que venzan las subidas del dia anterior.
  - StartWhenAvailable: si la PC estaba apagada a las 19:20, corre al prender. Subir
    tarde no molesta a nadie, a diferencia de la cola del grupo.
  - ExecutionTimeLimit 1 hora: 20 s entre subidas y videos de pocos MB.

Uso:
    powershell -ExecutionPolicy Bypass -File instalar-tarea-youtube-lanny.ps1
    powershell -ExecutionPolicy Bypass -File instalar-tarea-youtube-lanny.ps1 -Desinstalar
#>

param([switch]$Desinstalar)

$ErrorActionPreference = "Stop"
$nombre = "YouTubeLanny"
$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Definition
# La base, el .env y los videos viven en la carpeta principal del bot, no en un worktree.
$bot = "E:\dev\07-tools-personal\shopee-affiliate-bot"

if (Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Host "Borrada la version anterior de $nombre"
}
if ($Desinstalar) {
    Write-Host "Listo. Ya no se sube nada a YouTube solo."
    return
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No encuentro python.exe en el PATH." }
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No encuentro pythonw.exe junto a $python" }

$log = Join-Path $bot "logs\youtube_lanny.log"
$db = Join-Path $bot "grabados.db"
$accion = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "scripts\youtube_lanny.py --db `"$db`" lote --log `"$log`"" -WorkingDirectory $proyecto
$inicio = [datetime]::Today.AddHours(19).AddMinutes(20)
$disparador = New-ScheduledTaskTrigger -Daily -At $inicio
$disparador.Repetition = (New-ScheduledTaskTrigger -Once -At $inicio `
    -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Hours 1)).Repetition
$opciones = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador `
    -Settings $opciones -Principal $principal `
    -Description "Sube los Shorts de Lanny a su canal de YouTube (lote diario)" | Out-Null

Write-Host "Creada: $nombre, todos los dias a las 19:20 con reintentos 1 hora, desde $proyecto."
Write-Host "Registro: $log"
