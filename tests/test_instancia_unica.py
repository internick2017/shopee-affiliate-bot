"""Tests del candado de instancia unica.

Por que existe: la tarea programada reintenta arrancar el bot cada 2 minutos. El
ajuste IgnoreNew de Windows solo conoce las instancias que arranco ESA tarea, asi
que no ve un bot lanzado a mano por .vbs ni uno que sobrevivio a re-registrar la
tarea. Sin este candado, medido en vivo, quedaron DOS run_ofertas.py corriendo y
eso publica cada oferta dos veces en el canal.
"""

import multiprocessing
import sys

import pytest

from src.instancia_unica import ya_hay_otra_instancia


@pytest.fixture(autouse=True)
def _soltar_candados():
    """El registro de candados es global al PROCESO (a proposito: mientras el bot
    viva, el archivo tiene que seguir abierto). En los tests hay que soltarlo, si
    no el segundo test hereda el candado del primero."""
    from src import instancia_unica

    yield
    for archivo in instancia_unica._ABIERTOS.values():
        archivo.close()
    instancia_unica._ABIERTOS.clear()


def test_la_primera_instancia_puede_arrancar(tmp_path):
    assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is False


def test_la_segunda_instancia_del_mismo_proceso_no_arranca(tmp_path):
    assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is False
    assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is True


def test_dos_bots_distintos_no_se_estorban(tmp_path):
    assert ya_hay_otra_instancia("ofertas", carpeta=tmp_path) is False
    assert ya_hay_otra_instancia("generador", carpeta=tmp_path) is False


def _tomar_candado(carpeta, resultado):
    from src.instancia_unica import ya_hay_otra_instancia

    resultado.value = ya_hay_otra_instancia("probe", carpeta=carpeta)
    # Se queda vivo hasta que el test lo termine, sosteniendo el candado.
    import time

    time.sleep(30)


@pytest.mark.skipif(sys.platform != "win32", reason="el escenario real es Windows")
def test_otro_proceso_vivo_bloquea(tmp_path):
    """El caso de verdad: OTRO proceso tiene el candado."""
    resultado = multiprocessing.Value("b", False)
    hijo = multiprocessing.Process(target=_tomar_candado, args=(str(tmp_path), resultado))
    hijo.start()
    try:
        for _ in range(100):
            if hijo.is_alive() and (tmp_path / "probe.lock").exists():
                break
            import time

            time.sleep(0.1)
        import time

        time.sleep(1.0)
        assert resultado.value == 0, "el hijo tendria que haber tomado el candado"
        assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is True
    finally:
        hijo.terminate()
        hijo.join(timeout=5)


@pytest.mark.skipif(sys.platform != "win32", reason="el escenario real es Windows")
def test_si_el_otro_proceso_muere_se_libera(tmp_path):
    """Un bot que crashea no puede dejar el candado trabado para siempre: si no,
    la tarea programada nunca lo podria volver a levantar."""
    resultado = multiprocessing.Value("b", False)
    hijo = multiprocessing.Process(target=_tomar_candado, args=(str(tmp_path), resultado))
    hijo.start()
    import time

    time.sleep(2.0)
    assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is True
    hijo.terminate()
    hijo.join(timeout=5)
    time.sleep(1.0)
    assert ya_hay_otra_instancia("probe", carpeta=tmp_path) is False
