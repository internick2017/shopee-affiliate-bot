"""Copia las ventas de Shopee (Lanny y Nick) y los videos grabados al panel de
reportes en Supabase. Corre cada 4 horas como tarea programada (ShopeePanelSync,
ver instalar-tareas.ps1); tambien se puede correr a mano para ver que pasa.

Uso:
    python sync_panel.py

Sale con 0 si todo anduvo, 1 si alguna cuenta o los videos fallaron (el detalle
queda en logs/sync_panel.log y en la tabla `sincronizacion` del panel), y 2 si
falta configuracion en el .env.
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from src.grabados_store import VideosStore
from src.logging_setup import configurar_logging
from src.panel_sync import Supabase, sincronizar, traer_marcas

_RAIZ = Path(__file__).resolve().parent

# Cuenta del panel: (variable del app id, variable del secret) en el .env.
_CUENTAS = {
    "lanny": ("SHOPEE_APP_ID", "SHOPEE_SECRET"),
    "nick": ("SHOPEE_APP_ID_NICK", "SHOPEE_SECRET_NICK"),
}


def main() -> int:
    # Ruta explicita: load_dotenv() pelado busca desde el directorio actual y ya dio
    # un falso "Invalid Credential" corriendo desde otra carpeta.
    load_dotenv(_RAIZ / ".env")
    logger = configurar_logging("sync-panel", _RAIZ / "logs" / "sync_panel.log")

    faltan = [v for v in ("SUPABASE_PANEL_URL", "SUPABASE_PANEL_SERVICE_KEY")
              if not os.environ.get(v)]
    faltan += [v for par in _CUENTAS.values() for v in par if not os.environ.get(v)]
    if faltan:
        logger.error("Faltan variables en el .env: %s", ", ".join(faltan))
        return 2

    cuentas = {c: (os.environ[a], os.environ[s]) for c, (a, s) in _CUENTAS.items()}
    db = Supabase(os.environ["SUPABASE_PANEL_URL"], os.environ["SUPABASE_PANEL_SERVICE_KEY"])
    store = VideosStore(_RAIZ / "grabados.db")
    # Primero las marcas del panel: asi `publicado_en` sube completo y la copia de
    # los videos nunca pisa una marca.
    marcadas, consumidas, error_marcas = traer_marcas(db, store)
    if error_marcas:
        logger.error(error_marcas)
    else:
        logger.info("Marcas del panel aplicadas: %d", marcadas)
    videos = store.listar(cuantos=100_000)

    resultado = sincronizar(cuentas, videos, db, ahora=datetime.now(UTC),
                            error_marcas=error_marcas, marcas_consumidas=consumidas)
    for nombre, ok in resultado.items():
        (logger.info if ok else logger.error)("%s: %s", nombre, "ok" if ok else "FALLO")
    return 0 if all(resultado.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
