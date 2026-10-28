<#
Crea (o actualiza) la tarea programada que manda la cola del grupo de WhatsApp de Lanny.

Corre scripts\cola_whatsapp.py enviar --enviar cada 5 minutos, de 8:00 a 21:50, de
lunes a sabado. Cada post tiene su minuto al azar (8:07, 8:41...): la corrida que
lo encuentra vencido lo manda. La primera corrida del dia arma la cola (28 posts,
80 % hogar); cada corrida manda UN post, el que toca, desde el celular de Nick.

Decisiones:
  - Las corridas sin post vencido no tocan el celular: solo leen la cola.
  - Sin StartWhenAvailable: si la PC estaba apagada, esos posts se dan por vencidos.
    Recuperarlos todos juntos seria una rafaga en el grupo.
  - ExecutionTimeLimit 15 minutos: el script espera hasta 10 si el publicador de
    Shopee Video tiene el celular.

Uso:
    powershell -ExecutionPolicy Bypass -File instalar-tarea-cola-whatsapp.ps1
    powershell -ExecutionPolicy Bypass -File instalar-tarea-cola-whatsapp.ps1 -Desinstalar
#>

param([switch]$Desinstalar)

$ErrorActionPreference = "Stop"
$nombre = "ColaWhatsApp"
$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Definition

if (Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Host "Borrada la version anterior de $nombre"
}
if ($Desinstalar) {
    Write-Host "Listo. Ya no se manda nada al grupo."
    return
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No encuentro python.exe en el PATH." }
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No encuentro pythonw.exe junto a $python" }

$accion = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "scripts\cola_whatsapp.py enviar --enviar" -WorkingDirectory $proyecto
$disparador = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday, Saturday `
    -At ([datetime]::Today.AddHours(8))
# 8:00 + 13 h 51 min: la ultima corrida es 21:50, despues del ultimo post (21:45 como mucho).
$disparador.Repetition = (New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(8)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Hours 13 -Minutes 51)).Repetition
$opciones = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador `
    -Settings $opciones -Principal $principal `
    -Description "Manda la cola diaria al grupo de WhatsApp de Lanny desde el celular" | Out-Null

Write-Host "Creada: $nombre, cada 5 min de 8:00 a 21:50, lunes a sabado."
Write-Host "Registro: $proyecto\logs\cola_whatsapp.log"
