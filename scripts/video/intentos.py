"""Registro de prompts: que se pidio en cada video y como salio.

YouTube Create anota cada intento solo (`youtube_create.py`). Lo demas se anota asi:
    python scripts/video/intentos.py registrar <nombre> "<herramienta>" "<prompt>" [gancho] [item_id]
    python scripts/video/intentos.py marcar <nombre> ok [video.mp4]
    python scripts/video/intentos.py marcar <nombre> defecto "<que fallo>" [video.mp4]
    python scripts/video/intentos.py informe
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from src.grabados_store import IntentosStore  # noqa: E402
from src.panel_sync import leer_conversiones  # noqa: E402
from src.video_canal import credenciales  # noqa: E402


def ventas_shopee_video() -> Counter[int]:
    """Ventas por producto en Shopee Video de las dos cuentas, ultimos 90 dias (lo maximo de la API)."""
    load_dotenv(RAIZ / ".env")
    ventas: Counter[int] = Counter()
    hasta = int(time.time())
    for cuenta in ("lanny", "nick"):
        nodos, error = leer_conversiones(*credenciales(cuenta), desde=hasta - 90 * 86400 + 60, hasta=hasta)
        if error:
            print(f"OJO: ventas de {cuenta} incompletas: {error}")
        for n in nodos:
            if (n.get("referrer") or "").startswith("Shopeevideo"):
                for o in n.get("orders") or []:
                    for it in o.get("items") or []:
                        if "CANCEL" not in (it.get("displayItemStatus") or ""):
                            ventas[int(it.get("itemId") or 0)] += 1
    return ventas


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    store = IntentosStore(RAIZ / "grabados.db")
    match sys.argv[1:]:
        case ["registrar", nombre, herramienta, prompt, *resto]:
            gancho = resto[0] if resto else "sin gancho"
            item_id = int(resto[1]) if len(resto) > 1 else None
            store.registrar(nombre, herramienta=herramienta, prompt=prompt, estado="generado",
                            gancho=gancho, item_id=item_id)
        case ["marcar", nombre, "ok" | "defecto" as estado, *resto]:
            video = Path(resto[-1]) if resto and resto[-1].endswith(".mp4") else None
            nota = resto[0] if estado == "defecto" and resto else ""
            medido = None
            if video:
                from src.fidelidad import cuadros, movimiento
                medido = round(movimiento(cuadros(video)), 1)
            if not store.marcar(nombre, estado, nota=nota, movimiento=medido):
                print(f"No hay intentos de {nombre}")
                return 1
        case ["informe"]:
            print("gancho | intentos | ok | defecto | movimiento")
            for gancho, total, ok, defecto, mov in store.informe():
                print(f"{gancho} | {total} | {ok} | {defecto} | {mov}")
            print("\ngrupo | intentos | ok | defecto | ventas en Shopee Video")
            for grupo, total, ok, defecto, vendidas in store.comparar(ventas_shopee_video()):
                print(f"{grupo} | {total} | {ok} | {defecto} | {vendidas}")
            for nombre, nota, prompt in store.defectos():
                print(f"\n{nombre}: {nota}\n  {prompt}")
        case _:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
