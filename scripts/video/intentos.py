"""Registro de prompts: que se pidio en cada video y como salio.

YouTube Create anota cada intento solo (`youtube_create.py`). Lo demas se anota asi:
    python scripts/video/intentos.py registrar <nombre> "<herramienta>" "<prompt>" [gancho] [item_id]
    python scripts/video/intentos.py marcar <nombre> ok [video.mp4]
    python scripts/video/intentos.py marcar <nombre> defecto "<que fallo>" [video.mp4]
    python scripts/video/intentos.py informe
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.grabados_store import IntentosStore  # noqa: E402


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
            for nombre, nota, prompt in store.defectos():
                print(f"\n{nombre}: {nota}\n  {prompt}")
        case _:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
