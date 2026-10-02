<#
Crea (o actualiza) las tareas programadas que mantienen los dos bots corriendo.

Por que existe: antes los bots se lanzaban con los .vbs del escritorio. Eso los
arrancaba, pero no los VOLVIA a arrancar: si el proceso se moria (internet caido,
excepcion, API de Shopee con error), quedaba muerto hasta que alguien hacia doble
clic de nuevo, y como corrian ocultos no habia forma de enterarse.

El Programador de tareas de Windows resuelve las dos cosas:
  - arranca los bots al iniciar sesion, sin que nadie haga clic;
  - los vuelve a levantar solos si se caen.

Como se logra lo segundo, que NO es obvio: la tarea se intenta arrancar cada 2
minutos para siempre, con MultipleInstances=IgnoreNew. Si el bot esta vivo,
Windows ve que ya hay una instancia y no hace nada (no cuesta nada). Si esta
muerto, lo levanta. Como maximo se pierden 2 minutos.

Se probo primero la opcion "reiniciar si la tarea falla" (RestartCount), que
parece la natural, y NO funciono: al matar el proceso desde afuera Windows
registro el fallo (LastTaskResult -1) pero nunca reinicio. Se deja igual como
red de seguridad, pero el que realmente sostiene el 24/7 es el disparador
repetido.

Se usa pythonw.exe y no python.exe para que no aparezca una ventana negra.
Sin consola, lo que se imprime en pantalla se pierde: por eso los bots ahora
escriben tambien a logs\*.log (ver src/logging_setup.py).

Uso:
    powershell -ExecutionPolicy Bypass -File instalar-tareas.ps1
    powershell -ExecutionPolicy Bypass -File instalar-tareas.ps1 -Desinstalar
#>

param(
    [switch]$Desinstalar,
    # Registra solo la sincronizacion del panel, sin tocar las tareas de los bots
    # (re-registrarlas reinicia los bots que estan corriendo).
    [switch]$SoloPanel
)

$ErrorActionPreference = "Stop"

$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Definition
$tareas = @(
    @{ Nombre = "ShopeeBotOfertas";   Script = "run_ofertas.py";   Que = "Bot de ofertas (fuentes -> canal Lanny)" },
    @{ Nombre = "ShopeeBotGenerador"; Script = "bot_generador.py"; Que = "Bot generador de posts (Telegram privado)" }
)

# La sincronizacion del panel de reportes NO es un bot: corre, copia las ventas y
# los videos a Supabase y termina. Por eso va aparte, con otro disparador.
$panel = @{ Nombre = "ShopeePanelSync"; Script = "sync_panel.py"; Que = "Copia ventas y videos al panel de reportes (cada 4 h)" }

if ($Desinstalar) {
    foreach ($t in $tareas + @($panel)) {
        if (Get-ScheduledTask -TaskName $t.Nombre -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $t.Nombre -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false
            Write-Host "Borrada: $($t.Nombre)"
        }
        else {
            Write-Host "No existia: $($t.Nombre)"
        }
    }
    Write-Host ""
    Write-Host "Listo. Los bots ya no arrancan solos."
    return
}

# pythonw.exe al lado del python.exe que este en el PATH. Si se resolviera a mano
# se romperia en cuanto Nick actualice Python.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No encuentro python.exe en el PATH." }
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No encuentro pythonw.exe junto a $python" }

Write-Host "Proyecto: $proyecto"
Write-Host "Python:   $pythonw"
Write-Host ""

foreach ($t in $(if ($SoloPanel) { @() } else { $tareas })) {
    $accion = New-ScheduledTaskAction -Execute $pythonw -Argument $t.Script -WorkingDirectory $proyecto
    # DOS disparadores, y hacen falta los dos:
    #
    #  - AtLogOn: arranca el bot cuando Nick inicia sesion (el caso "prendio la PC").
    #  - Once + repeticion cada 2 minutos: es el que sostiene el 24/7.
    #
    # Al principio se puso la repeticion SOBRE el AtLogOn, y no funciono: un
    # disparador de inicio de sesion recien empieza a repetir cuando ocurre el
    # inicio de sesion, asi que en la sesion ya abierta nunca arrancaba
    # (NextRunTime quedaba vacio) y el bot muerto no revivia hasta el proximo
    # reinicio. El -Once con fecha de arranque en el pasado empieza a repetir ya.
    $alIniciarSesion = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $cadaDosMinutos = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(-1) `
        -RepetitionInterval (New-TimeSpan -Minutes 2)
    # Duration vacio = repetir indefinidamente. Poner un valor explicito (incluso
    # TimeSpan::MaxValue o cero) hace que Windows rechace el XML con 0x80041318.
    $cadaDosMinutos.Repetition.Duration = $null
    $cadaDosMinutos.Repetition.StopAtDurationEnd = $false
    $disparador = @($alIniciarSesion, $cadaDosMinutos)

    # RestartInterval/RestartCount: red de seguridad para cuando la tarea falla al
    # arrancar. NO alcanza por si solo (ver comentario de arriba).
    # IgnoreNew es lo que hace que el reintento cada 2 minutos sea inofensivo:
    # con el bot vivo, la corrida repetida se descarta sin abrir un segundo proceso.
    # ExecutionTimeLimit 0 = sin limite de tiempo; es un proceso que no termina nunca,
    # y el default de Windows (3 dias) lo mataria en silencio.
    # IgnoreNew = si ya hay una instancia corriendo, no arranca una segunda.
    $opciones = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -RestartCount 99 `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
        -MultipleInstances IgnoreNew

    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

    if (Get-ScheduledTask -TaskName $t.Nombre -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false
    }
    Register-ScheduledTask -TaskName $t.Nombre -Action $accion -Trigger $disparador `
        -Settings $opciones -Principal $principal -Description $t.Que | Out-Null
    Write-Host "Creada: $($t.Nombre)  ->  $($t.Script)"
}

# Sincronizacion del panel. Tres diferencias con los bots, a proposito:
#  - Repite cada 4 horas, no cada 2 minutos: no es un proceso que haya que revivir,
#    es una corrida que empieza y termina.
#  - ExecutionTimeLimit de 30 minutos: una corrida normal tarda segundos; si se
#    cuelga (red), Windows la corta y la proxima arranca limpia.
#  - Sin AtLogOn: StartWhenAvailable ya cubre "la PC estaba apagada a la hora",
#    corre apenas puede.
# Misma trampa que arriba con Duration: vacio = repetir para siempre.
$accionPanel = New-ScheduledTaskAction -Execute $pythonw -Argument $panel.Script -WorkingDirectory $proyecto
$cadaCuatroHoras = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(-1) `
    -RepetitionInterval (New-TimeSpan -Hours 4)
$cadaCuatroHoras.Repetition.Duration = $null
$cadaCuatroHoras.Repetition.StopAtDurationEnd = $false
$opcionesPanel = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew
$principalPanel = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
if (Get-ScheduledTask -TaskName $panel.Nombre -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $panel.Nombre -Confirm:$false
}
Register-ScheduledTask -TaskName $panel.Nombre -Action $accionPanel -Trigger $cadaCuatroHoras `
    -Settings $opcionesPanel -Principal $principalPanel -Description $panel.Que | Out-Null
Write-Host "Creada: $($panel.Nombre)  ->  $($panel.Script)"

if ($SoloPanel) {
    Write-Host ""
    Write-Host "Listo. El panel se sincroniza cada 4 horas. Para correrlo AHORA:"
    Write-Host "    Start-ScheduledTask -TaskName ShopeePanelSync"
    return
}

Write-Host ""
Write-Host "Listo. Los bots arrancan solos al iniciar sesion y se reinician si se caen."
Write-Host "Para arrancarlos AHORA sin reiniciar la sesion:"
Write-Host "    Start-ScheduledTask -TaskName ShopeeBotOfertas"
Write-Host "    Start-ScheduledTask -TaskName ShopeeBotGenerador"
Write-Host "Los logs quedan en: $proyecto\logs\"
