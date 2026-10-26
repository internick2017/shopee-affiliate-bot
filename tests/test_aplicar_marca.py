import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "video"))

from aplicar_marca import filtro  # noqa: E402


def test_sin_foto_solo_la_marca_abajo_a_la_derecha():
    f = filtro(False)
    assert "[2:v]" not in f and "overlay=W-w-" in f


def test_con_foto_va_arriba_a_la_izquierda_y_la_marca_sigue_abajo():
    f = filtro(True)
    assert "[2:v]" in f
    assert "overlay=24:150" in f          # foto: esquina superior izquierda
    assert f.rstrip().endswith("overlay=W-w-28:H-h-28")  # marca: sin cambios
