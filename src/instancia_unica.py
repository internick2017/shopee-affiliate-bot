"""Candado para que un bot no corra dos veces al mismo tiempo.

Por que hace falta: los bots los levanta una tarea programada que se reintenta
cada 2 minutos (ver instalar-tareas.ps1). El ajuste MultipleInstances=IgnoreNew
de Windows NO alcanza, porque solo conoce las instancias que arranco esa misma
tarea: no ve un bot lanzado a mano con los .vbs, ni uno que quedo vivo despues de
re-registrar la tarea. Medido en vivo el 2026-08-29, asi quedaron dos
run_ofertas.py corriendo a la vez, que publica cada oferta DOS VECES en el canal.

El candado es un archivo bloqueado por el sistema operativo, no un archivo con el
PID adentro. La diferencia importa: si el bot crashea, el sistema libera el bloqueo
solo, y la tarea lo puede volver a levantar. Un archivo con el PID quedaria
trabado para siempre despues de un corte de luz.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Los archivos abiertos se guardan a proposito en una global: mientras el proceso
# viva, el archivo sigue abierto y el bloqueo sigue puesto. Si se los dejara como
# variables locales, el recolector los cerraria y liberaria el candado.
_ABIERTOS: dict[str, object] = {}


def ya_hay_otra_instancia(nombre: str, carpeta: str | Path = ".") -> bool:
    """True si ya hay otro proceso corriendo este bot; False si se puede arrancar.

    Al devolver False deja el candado tomado hasta que el proceso termine."""
    ruta = Path(carpeta) / f"{nombre}.lock"
    ruta.parent.mkdir(parents=True, exist_ok=True)

    if nombre in _ABIERTOS:
        return True

    try:
        # noqa a proposito: el archivo NO se cierra, y eso es el punto. El
        # candado dura mientras el archivo este abierto, o sea toda la vida
        # del proceso. Un context manager lo cerraria y lo liberaria.
        archivo = open(ruta, "a+b")  # noqa: SIM115
    except OSError:
        # Si no se puede ni abrir el archivo, no se bloquea el arranque: es peor
        # dejar el bot caido que arriesgar un duplicado.
        return False

    if not _bloquear(archivo):
        archivo.close()
        return True

    _ABIERTOS[nombre] = archivo
    return False


def _bloquear(archivo) -> bool:
    """Bloqueo exclusivo y NO bloqueante. False si ya lo tiene otro proceso."""
    try:
        if sys.platform == "win32":
            import msvcrt

            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True
