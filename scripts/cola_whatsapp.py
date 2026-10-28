"""Cola diaria del grupo de WhatsApp de Lanny: arma la del dia y manda el post que toca.

Uso (desde la raiz del repo):

    python scripts/cola_whatsapp.py ver               # arma la de hoy y la muestra, sin guardar
    python scripts/cola_whatsapp.py armar             # arma y guarda la de hoy (si ya existe, no hace nada)
    python scripts/cola_whatsapp.py enviar            # en seco: abre el grupo, escribe y NO manda
    python scripts/cola_whatsapp.py enviar --enviar   # manda de verdad el post que toca

La tarea programada ColaWhatsApp corre `enviar --enviar` cada 5 minutos de lunes a
sabado; `enviar` arma la cola del dia si todavia no existe. Registro en
logs/cola_whatsapp.log, capturas en logs/cola_whatsapp/<fecha-hora>/, y la cola con
lo mandado en cola_whatsapp.db.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import msvcrt
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from src.cola_whatsapp import (  # noqa: E402
    CelularNoDisponible,
    ColaStore,
    EnvioAbortado,
    WhatsApp,
    a_enviar,
    armar_cola,
)
from src.logging_setup import configurar_logging  # noqa: E402
from src.post_builder import HookBank  # noqa: E402
from src.product_ideas import buscar_ideas  # noqa: E402
from src.publicador_celular import Pasos  # noqa: E402

# Cuanto esperar el celular si lo tiene el publicador de Shopee Video: una
# publicacion tarda unos 2 minutos.
ESPERA_CANDADO = 10 * 60


def cola_de_hoy(store: ColaStore, hoy: dt.date, *, guardar: bool):
    existente = store.del_dia(hoy)
    if existente:
        return existente
    app, sec = os.getenv("SHOPEE_APP_ID", ""), os.getenv("SHOPEE_SECRET", "")
    if not app or not sec:
        sys.exit("Faltan SHOPEE_APP_ID / SHOPEE_SECRET (cuenta de Lanny) en el .env")
    cola = armar_cola(
        hoy,
        lambda b, excluir: buscar_ideas(b, app, sec, cuantas=50, candidatos=50, excluir=excluir),
        HookBank.from_file(RAIZ / "hooks.txt"),
        excluir=store.de_la_semana(hoy),
    )
    if guardar:
        store.guardar(cola)
    return cola


def tomar_celular(log):
    """El mismo candado que el publicador de Shopee Video: un solo dueño del celular."""
    candado = open(RAIZ / "logs" / "publicador.lock", "w")  # noqa: SIM115 abierto toda la corrida
    limite = time.time() + ESPERA_CANDADO
    while True:
        try:
            msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)
            return candado
        except OSError:
            if time.time() > limite:
                log.info("El celular sigue ocupado con otra publicacion: salteo este turno.")
                return None
            time.sleep(30)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["ver", "armar", "enviar"])
    ap.add_argument("--enviar", action="store_true", help="mandar de verdad (sin esto, en seco)")
    args = ap.parse_args()

    load_dotenv(RAIZ / ".env")
    log = configurar_logging("cola-whatsapp", RAIZ / "logs" / "cola_whatsapp.log")
    store = ColaStore(RAIZ / "cola_whatsapp.db")
    hoy = dt.date.today()

    if args.accion == "ver":
        # Solo aca se imprime: la tarea corre con pythonw, que no tiene sys.stdout.
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        for e in cola_de_hoy(store, hoy, guardar=False):
            print(f"{e.hora} [{e.rubro}] {e.estado}  {e.titulo[:70]}")
        return 0

    cola = cola_de_hoy(store, hoy, guardar=True)
    if args.accion == "armar":
        log.info("Cola del %s: %d posts", hoy, len(cola))
        return 0

    toca, viejos = a_enviar(cola, dt.datetime.now())
    if args.enviar:  # en seco no se toca la cola
        for e in viejos:
            store.marcar(e, "vencido")
    if toca is None:
        log.info("Nada para mandar ahora.")
        return 0

    texto, ml = toca.texto, None
    if toca.rubro == "ml":
        ml = store.candidato_ml(dt.datetime.now())
        if ml is None:
            log.info("Sin oferta de ML fresca de hogar: va el respaldo de Shopee")
        else:
            texto = ml[2]

    candado = tomar_celular(log)
    if candado is None:
        return 0
    pasos = Pasos(RAIZ / "logs" / "cola_whatsapp" / time.strftime("%Y%m%d-%H%M%S"))
    try:
        wa = WhatsApp.conectar(pasos)
        wa.abrir_grupo(os.environ["WHATSAPP_GRUPO_LINK"])
        wa.mandar(texto, enviar=args.enviar)
    except CelularNoDisponible as exc:
        log.info("No mando %s todavia: %s. Pruebo en la proxima corrida.", toca.hora, exc)
        return 0
    except EnvioAbortado as exc:
        log.error("No se mando %s %s: %s", toca.hora, toca.titulo, exc)
        if args.enviar:
            store.marcar(toca, "fallido")
        return 1
    except Exception:
        # Celular desconectado, ADB caido: el post queda pendiente para la proxima.
        log.exception("No pude manejar el celular para %s", toca.hora)
        return 1
    if args.enviar:
        if ml is not None:
            store.reemplazar(toca, ml[1], ml[2])
            store.marcar_ml_enviado(ml[0])
        store.marcar(toca, "enviado")
        log.info("Mandado %s [%s] %s", toca.hora, toca.rubro, toca.titulo)
    else:
        log.info("En seco: %s quedo escrito y no se mando", ml[1] if ml else toca.titulo)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # La tarea corre con pythonw, sin ventana: si no queda en el log, no queda en ningun lado.
        configurar_logging("cola-whatsapp", RAIZ / "logs" / "cola_whatsapp.log").exception("La cola se cayo")
        sys.exit(1)
