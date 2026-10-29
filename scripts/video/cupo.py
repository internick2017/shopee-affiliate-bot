"""Conteo real de generaciones de video por dia, por herramienta y por cuenta.

Existe porque el cupo diario de las herramientas de video se pierde de vista y Nick
tenia que repetirlo en cada sesion (2026-10-24: YouTube Create dio "limite" en tres
cuentas sin que nadie llevara la cuenta). Cada intento, bueno o rechazado, se anota
UNA linea en `cupo_diario.jsonl` (ignorado por git, vive en la raiz del repo).

Uso:
    python cupo.py registrar "YouTube Create" internickbr --nota "conjunto3"
    python cupo.py registrar "YouTube Create" internickbr --limite
    python cupo.py registrar "Flow Music" sugarysalamander --creditos 125
    python cupo.py hoy                  # cuenta por herramienta y cuenta
    python cupo.py hoy --fecha 2026-10-24

`--limite` marca que la herramienta rechazo el intento ("Voce alcancou o limite"):
no cuenta como generacion, pero fija cuantas entraron antes de que cortara. Asi,
despues de unos dias, `hoy` muestra el tope real de cada cuenta en vez de un supuesto.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parents[2] / "cupo_diario.jsonl"


def registrar(herramienta: str, cuenta: str, *, limite: bool = False,
              creditos: int | None = None, nota: str = "",
              ts: datetime | None = None) -> dict:
    fila = {
        "ts": (ts or datetime.now()).isoformat(timespec="seconds"),
        "herramienta": herramienta,
        "cuenta": cuenta,
        "limite": limite,
        "creditos": creditos,
        "nota": nota,
    }
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def leer(fecha: str) -> list[dict]:
    if not ARCHIVO.exists():
        return []
    filas = [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [f for f in filas if f["ts"].startswith(fecha)]


def resumen(fecha: str) -> str:
    filas = leer(fecha)
    if not filas:
        return f"{fecha}: sin intentos registrados."
    por = defaultdict(lambda: {"ok": 0, "limite": None, "creditos": 0})
    for f in filas:
        d = por[(f["herramienta"], f["cuenta"])]
        if f["limite"]:
            d["limite"] = d["limite"] or f["ts"][11:16]
        else:
            d["ok"] += 1
            d["creditos"] += f["creditos"] or 0
    out = [f"{fecha}: generaciones por herramienta y cuenta"]
    for (h, c), d in sorted(por.items()):
        cortada = f", cortada {d['limite']} (despues de {d['ok']})" if d["limite"] else ""
        cred = f", {d['creditos']} creditos" if d["creditos"] else ""
        out.append(f"  {h} / {c}: {d['ok']}{cred}{cortada}")
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("registrar")
    r.add_argument("herramienta")
    r.add_argument("cuenta")
    r.add_argument("--limite", action="store_true")
    r.add_argument("--creditos", type=int)
    r.add_argument("--nota", default="")
    h = sub.add_parser("hoy")
    h.add_argument("--fecha", default=datetime.now().strftime("%Y-%m-%d"))
    a = p.parse_args()
    if a.cmd == "registrar":
        registrar(a.herramienta, a.cuenta, limite=a.limite, creditos=a.creditos, nota=a.nota)
        print(resumen(datetime.now().strftime("%Y-%m-%d")))
    else:
        print(resumen(a.fecha))


if __name__ == "__main__":
    main()
