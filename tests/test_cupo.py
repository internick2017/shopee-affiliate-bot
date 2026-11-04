import importlib.util
from datetime import datetime
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cupo", Path(__file__).resolve().parents[1] / "scripts" / "video" / "cupo.py")
cupo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cupo)


def fila(ts, cuenta, creditos, limite=False, herramienta="Flow"):
    return {"ts": ts, "herramienta": herramienta, "cuenta": cuenta,
            "limite": limite, "creditos": creditos, "nota": ""}


def test_saldo_descuenta_solo_desde_la_ultima_renovacion():
    filas = [
        fila("2026-11-04T01:00:00", "setupjustobr", 12),  # antes de renovar a la 01:14: no cuenta
        fila("2026-11-04T09:20:00", "setupjustobr", 12),
        fila("2026-11-04T09:30:00", "setupjustobr", 12),
        fila("2026-11-04T09:40:00", "setupjustobr", 12, limite=True),  # rechazado: no cobra
        fila("2026-11-04T09:45:00", "setupjustobr", 125, herramienta="Flow Music"),
    ]
    s = cupo.saldos(filas, datetime(2026, 11, 4, 10, 0))
    assert s["setupjustobr"] == (24, 26)
    assert s["marketing.aresmkt"] == (0, 50)


def test_renovacion_de_la_noche_cuenta_desde_ayer():
    filas = [fila("2026-11-03T21:00:00", "nick.daniel@apikiwp", 48)]
    assert cupo.saldos(filas, datetime(2026, 11, 4, 10, 0))["nick.daniel@apikiwp"] == (48, 2)
    assert cupo.saldos(filas, datetime(2026, 11, 4, 20, 30))["nick.daniel@apikiwp"] == (0, 50)
