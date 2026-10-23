"""Publica en Shopee Video el siguiente video pendiente, manejando el celular.

Uso (desde la raiz del repo, con el celular conectado por ADB):

    python scripts/publicar_video.py                 # en seco: carga todo y NO publica
    python scripts/publicar_video.py --postar        # publica de verdad
    python scripts/publicar_video.py --item-id 123   # un video puntual en vez del siguiente

Por defecto es en seco a proposito: publicar es lo unico que no se puede deshacer.
La tarea programada ShopeePublicarVideo (instalar-tarea-publicador.ps1) lo corre con
--postar varias veces por dia, un video por corrida.

Al publicar, ademas de marcarlo en grabados.db, sube ese video al panel de afiliados
para que se vea como publicado en el momento (si no, esperaria la sync de 4 horas).
Las capturas de cada paso quedan en logs/publicador/<fecha-hora>/ y el registro en
logs/publicador.log.
"""

from __future__ import annotations

import argparse
import msvcrt
import os
import random
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from src.grabados_store import VideosStore  # noqa: E402
from src.logging_setup import configurar_logging  # noqa: E402
from src.panel_sync import Supabase, subir_video  # noqa: E402
from src.publicador_celular import (  # noqa: E402
    TOPE_DIARIO,
    Celular,
    Pasos,
    PublicacionAbortada,
    publicados_hoy,
    publicar,
    siguiente_video,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canal", default="nick")
    ap.add_argument("--item-id", type=int)
    ap.add_argument("--postar", action="store_true", help="publicar de verdad (sin esto, en seco)")
    ap.add_argument("--aceptar-aviso", action="store_true",
                    help='pulsar "Postar de qualquer forma" si Shopee avisa de posible violacion de pautas')
    ap.add_argument("--saltar-verificacion", action="store_true",
                    help="no comparar el producto vinculado con el registrado (solo si lo confirmaste a mano)")
    ap.add_argument("--pagina-directa", action="store_true",
                    help="el link abre directo en la pagina completa, sin vista corta que tocar")
    ap.add_argument("--cantidad", type=int, default=1,
                    help="publicar varios seguidos (hasta el tope diario), con una pausa corta entre cada uno")
    args = ap.parse_args()

    # Ruta explicita: load_dotenv() pelado busca desde el directorio actual.
    load_dotenv(RAIZ / ".env")
    log = configurar_logging("publicador", RAIZ / "logs" / "publicador.log")

    # Una sola corrida a la vez: una rafaga a mano y la tarea programada tomarian el
    # mismo video (se marca publicado recien al final) y manejarian el celular a la vez.
    # Windows suelta el candado solo si el proceso muere.
    candado = open(RAIZ / "logs" / "publicador.lock", "w")  # noqa: SIM115 abierto toda la corrida
    try:
        msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log.info("Ya hay otra publicacion en curso: no arranco otra.")
        return 0

    store = VideosStore(RAIZ / "grabados.db")
    for i in range(args.cantidad if not args.item_id else 1):
        if i:
            time.sleep(random.uniform(45, 90))  # pausa entre videos, como una persona
        codigo, hubo_mas = _publicar_uno(args, store, log)
        if codigo or not hubo_mas:
            return codigo
    return 0


def _publicar_uno(args, store: VideosStore, log) -> tuple[int, bool]:
    """Un video. Devuelve (codigo de salida, si tiene sentido intentar otro)."""
    hoy = publicados_hoy(store, args.canal)
    if args.postar and hoy >= TOPE_DIARIO:
        log.info("Ya salieron %d videos hoy (tope %d): no publico mas hasta manana.", hoy, TOPE_DIARIO)
        return 0, False
    if args.item_id:
        video = next((v for v in store.sin_publicar(args.canal) if v.item_id == args.item_id), None)
    else:
        video = siguiente_video(store, args.canal)
    if video is None:
        log.info("No hay video pendiente listo para publicar (%s).", args.canal)
        return 0, False

    log.info("Video: %s | %s", video.item_id, video.titulo)
    pasos = Pasos(RAIZ / "logs" / "publicador" / time.strftime("%Y%m%d-%H%M%S"))
    try:
        celular = Celular.conectar(pasos)
    except Exception:
        log.exception("No pude conectar con el celular (cable, depuracion USB?)")
        return 1, False
    try:
        publico = publicar(
            store, video, celular, postar=args.postar, aceptar_aviso=args.aceptar_aviso,
            verificar=not args.saltar_verificacion, pagina_directa=args.pagina_directa,
        )
    except PublicacionAbortada as e:
        log.error("ABORTADO: %s. Capturas en %s", e, pasos.carpeta)
        celular.descartar()
        return 1, False
    except Exception:
        log.exception("Error inesperado. Capturas en %s", pasos.carpeta)
        celular.descartar()
        return 1, False

    if not publico:
        log.info("En seco OK, no se publico. Capturas en %s", pasos.carpeta)
        return 0, False
    log.info("PUBLICADO. Capturas en %s", pasos.carpeta)
    url, llave = os.environ.get("SUPABASE_PANEL_URL"), os.environ.get("SUPABASE_PANEL_SERVICE_KEY")
    if not url or not llave:
        log.warning("Sin credenciales del panel en el .env: lo marca la sync de las 4 horas")
        return 0, True
    actualizado = next(v for v in store.listar(args.canal, 100_000) if v.item_id == video.item_id)
    try:
        subir_video(Supabase(url, llave), actualizado)
        log.info("Marcado como publicado en el panel")
    except Exception as e:  # el video ya salio: el panel lo alcanza en la proxima sync
        log.warning("No pude marcarlo en el panel ahora (%s); lo hace la sync de las 4 horas", e)
    return 0, True


if __name__ == "__main__":
    sys.exit(main())
