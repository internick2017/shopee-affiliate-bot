"""Logging a archivo para los bots que corren 24/7 sin ventana.

Por que existe: los bots se lanzan ocultos (tarea programada de Windows), asi que
lo que se imprime en pantalla no lo ve nadie. Cuando la tarea reinicia un bot que
se cayo, el archivo es la unica evidencia de que paso. Antes de esto, un crash a
las 3 de la mañana no dejaba ningun rastro.

Rota por tamaño porque un proceso que nunca termina loguea para siempre.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMATO = "%(asctime)s %(levelname)s %(name)s %(message)s"

# 2 MB x 3 backups = 8 MB como maximo por bot. Alcanza de sobra para ver los dias
# anteriores y no le come el disco a nadie.
_MAX_BYTES = 2 * 1024 * 1024
_BACKUPS = 3

# Librerias que loguean la URL completa de cada request en INFO. El token del bot
# de Telegram va DENTRO de la URL, asi que en INFO terminariamos escribiendo el
# token en texto plano en el archivo, una y otra vez. En WARNING siguen avisando
# los errores, que es lo unico que necesitamos de ellas.
_RUIDOSOS = ("httpx", "httpcore", "telethon.network")


def configurar_logging(
    nombre: str,
    archivo: str | Path,
    *,
    nivel: int = logging.INFO,
    max_bytes: int = _MAX_BYTES,
    backups: int = _BACKUPS,
) -> logging.Logger:
    """Deja el logging escribiendo a pantalla Y a `archivo`, y devuelve el logger.

    Reemplaza al `logging.basicConfig(...)` que tenian los bots. La consola se
    mantiene a proposito: arrancar el bot a mano en una ventana para ver que hace
    es la forma mas rapida de diagnosticar, y no hay que perderla.

    Es idempotente: llamarla dos veces no duplica handlers (si no, cada linea
    aparaceria repetida en el archivo)."""
    ruta = Path(archivo)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(nivel)

    # Se limpian los handlers propios antes de agregar: asi una segunda llamada
    # reconfigura en vez de acumular.
    for viejo in list(root.handlers):
        if getattr(viejo, "_bot_handler", False):
            root.removeHandler(viejo)
            viejo.close()

    formato = logging.Formatter(_FORMATO)

    # Bajo pythonw.exe lanzado por el Programador de tareas no hay consola y
    # sys.stderr es None: un StreamHandler ahi falla en cada linea. Cuando SI hay
    # consola (arranque a mano) se mantiene, que es como se diagnostica rapido.
    if sys.stderr is not None:
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        consola._bot_handler = True  # type: ignore[attr-defined]
        root.addHandler(consola)

    # delay=True: no crea el archivo hasta la primera linea, para no dejar logs
    # vacios si el bot muere en el arranque por config.
    archivo_handler = RotatingFileHandler(
        ruta, maxBytes=max_bytes, backupCount=backups, encoding="utf-8", delay=True
    )
    archivo_handler.setFormatter(formato)
    archivo_handler._bot_handler = True  # type: ignore[attr-defined]
    root.addHandler(archivo_handler)

    for ruidoso in _RUIDOSOS:
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    return logging.getLogger(nombre)
