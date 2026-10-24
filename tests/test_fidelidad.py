import numpy as np

from src.fidelidad import MOV_MINIMO, movimiento


def test_foto_quieta_no_pasa_y_video_con_cambio_si():
    quieta = np.zeros((6, 112, 64))
    assert movimiento(quieta) < MOV_MINIMO
    moviendose = np.stack([np.full((112, 64), 20.0 * i) for i in range(6)])
    assert movimiento(moviendose) > MOV_MINIMO


def test_un_solo_cuadro_cuenta_como_sin_movimiento():
    assert movimiento(np.zeros((1, 112, 64))) == 0.0
