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


def test_fila_sin_creditos_y_correo_cuentan_para_la_misma_cuenta():
    filas = [fila("2026-11-05T09:00:00", "internick2017", None) for _ in range(4)]
    filas.append(fila("2026-11-05T09:30:00", "internick2017@gmail.com", 12))
    assert cupo.saldos(filas, datetime(2026, 11, 5, 10, 0))["internick2017"] == (60, 0)


def test_aviso_nombra_las_cuentas_con_diario():
    filas = [fila("2026-11-05T09:00:00", "internick2017", None) for _ in range(5)]
    msg = cupo.aviso_diario("internick2017@gmail.com", filas, datetime(2026, 11, 5, 10, 0))
    assert "pozo mensual" in msg and "setupjustobr (50)" in msg
    assert cupo.aviso_diario("setupjustobr", filas, datetime(2026, 11, 5, 10, 0)) is None
