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
    python cupo.py saldo                # cuanto queda hoy de los diarios de cada cuenta de Flow

`--limite` marca que la herramienta rechazo el intento ("Voce alcancou o limite"):
no cuenta como generacion, pero fija cuantas entraron antes de que cortara. Asi,
despues de unos dias, `hoy` muestra el tope real de cada cuenta en vez de un supuesto.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parents[2] / "cupo_diario.jsonl"

# Creditos diarios de Flow por cuenta y hora en que se renuevan (leidas en el menu de cuenta).
# Mapa completo de cuentas: vault, 10-projects/bot-afiliados/mapa-cuentas-flow-create.md.
# shortcut: las Pro no muestran la hora de sus 50 diarios; se asume 00:00 hasta medirla.
DIARIOS = {
    "internick2017": (50, "00:00"),
    "nick.inkaweb": (50, "00:00"),
    "nickgranados01": (50, "00:00"),
    "nick.daniel@apikiwp": (50, "20:10"),
    "marketing.aresmkt": (50, "01:43"),
    "setupjustobr": (50, "01:14"),
}
# Omni 720p 8 s; una fila de Flow sin --creditos cuenta esto (2026-11-05: 15 filas sin creditos
# dejaron el saldo de internick2017 en "0 gastado" y se comio 200 puntos del pozo mensual).
COSTO_FLOW = 12


def cuenta_canonica(cuenta: str) -> str:
    """'internick2017@gmail.com' y 'internick2017' son la misma cuenta."""
    return cuenta.removesuffix("@gmail.com")


def costo(f: dict) -> int:
    return COSTO_FLOW if f["creditos"] is None else f["creditos"]


def ultima_renovacion(hora: str, ahora: datetime) -> datetime:
    h, m = map(int, hora.split(":"))
    r = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    return r if r <= ahora else r - timedelta(days=1)


def saldos(filas: list[dict], ahora: datetime) -> dict[str, tuple[int, int]]:
    """Por cuenta: (gastado desde su ultima renovacion, lo que queda de los diarios)."""
    out = {}
    for cuenta, (diario, hora) in DIARIOS.items():
        desde = ultima_renovacion(hora, ahora)
        gastado = sum(costo(f) for f in filas
                      if cuenta_canonica(f["cuenta"]) == cuenta and f["herramienta"] == "Flow" and not f["limite"]
                      and desde <= datetime.fromisoformat(f["ts"]) <= ahora)
        out[cuenta] = (gastado, max(diario - gastado, 0))
    return out


def todas() -> list[dict]:
    if not ARCHIVO.exists():
        return []
    return [json.loads(linea) for linea in ARCHIVO.read_text(encoding="utf-8").splitlines() if linea.strip()]


def registrar(herramienta: str, cuenta: str, *, limite: bool = False,
              creditos: int | None = None, nota: str = "",
              ts: datetime | None = None) -> dict:
    fila = {
        "ts": (ts or datetime.now()).isoformat(timespec="seconds"),
        "herramienta": herramienta,
        "cuenta": cuenta_canonica(cuenta),
        "limite": limite,
        "creditos": creditos,
        "nota": nota,
    }
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def aviso_diario(cuenta: str, filas: list[dict], ahora: datetime) -> str | None:
    """Si la cuenta ya no tiene diario, nombra las que si: el pozo mensual va ultimo."""
    s = saldos(filas, ahora)
    cuenta = cuenta_canonica(cuenta)
    if cuenta not in s or s[cuenta][1] > 0:
        return None
    libres = [f"{c} ({q})" for c, (_, q) in s.items() if q >= COSTO_FLOW]
    if not libres:
        return f"AVISO: {cuenta} sin diario y ninguna otra cuenta tiene; esto sale del pozo mensual."
    return f"AVISO: {cuenta} ya no tiene diario, esto sale del pozo mensual. Con diario: {', '.join(libres)}"


def leer(fecha: str) -> list[dict]:
    if not ARCHIVO.exists():
        return []
    filas = [json.loads(linea) for linea in ARCHIVO.read_text(encoding="utf-8").splitlines() if linea.strip()]
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
    sub.add_parser("saldo")
    a = p.parse_args()
    if a.cmd == "registrar":
        registrar(a.herramienta, a.cuenta, limite=a.limite, creditos=a.creditos, nota=a.nota)
        if a.herramienta == "Flow" and (msg := aviso_diario(a.cuenta, todas(), datetime.now())):
            print(msg)
        print(resumen(datetime.now().strftime("%Y-%m-%d")))
    elif a.cmd == "saldo":
        ahora = datetime.now()
        print("Flow, creditos diarios (gastado / queda; renueva):")
        for cuenta, (gastado, queda) in saldos(todas(), ahora).items():
            print(f"  {cuenta}: {gastado} / {queda}  (renueva {DIARIOS[cuenta][1]})")
    else:
        print(resumen(a.fecha))


if __name__ == "__main__":
    main()
