from datetime import UTC, datetime

from src.grabados_store import VideoProducido
from src.panel_sync import filas_de_ventas, filas_de_videos

_T = datetime(2026, 10, 2, tzinfo=UTC)

_CAMPOS_DE_NODO = {"purchaseTime", "clickTime", "referrer", "utmContent", "conversionId"}


def _nodo(**campos):
    """Un nodo de `conversionReport` con una orden y un item. Los campos de la
    conversion van al nodo; el resto, al item."""
    nodo = {"purchaseTime": 1790774580, "clickTime": 1790774000, "referrer": "WhatsApp",
            "utmContent": "", "conversionId": 111}
    item = {"itemId": 22, "modelId": 33, "itemName": "Webcam", "itemPrice": "139",
            "qty": 1, "itemTotalCommission": "3.7761", "displayItemStatus": "PENDING",
            "completeTime": 0, "imageUrl": "https://img/x", "categoryLv1Name": "Informatica"}
    for k, v in campos.items():
        (nodo if k in _CAMPOS_DE_NODO else item)[k] = v
    nodo["orders"] = [{"orderId": "ORD1", "items": [item]}]
    return nodo


def _video(**campos):
    base = dict(item_id=7, canal="nick", titulo="Cooler", link="https://s.shopee.com.br/x",
                precio=50.9, comision_pct=16.0, herramienta="Flow", marca="nickgranados",
                archivo="cooler_nick.mp4", ts=1790971306.0, publicado_ts=None)
    base.update(campos)
    return VideoProducido(**base)


def test_una_fila_por_item_con_la_clave_completa():
    nodo = _nodo()
    nodo["orders"][0]["items"].append(dict(nodo["orders"][0]["items"][0], itemId=44))
    filas = filas_de_ventas("nick", [nodo], vista_en=_T)
    assert len(filas) == 2
    assert {k: filas[0][k] for k in ("cuenta", "conversion_id", "order_id", "item_id", "model_id")} == {
        "cuenta": "nick", "conversion_id": 111, "order_id": "ORD1", "item_id": 22, "model_id": 33}
    assert filas[1]["item_id"] == 44


def test_completeTime_cero_queda_null():
    fila = filas_de_ventas("nick", [_nodo(completeTime=0)], vista_en=_T)[0]
    assert fila["completada_en"] is None


def test_completeTime_real_queda_en_utc():
    fila = filas_de_ventas("nick", [_nodo(completeTime=1790774580)], vista_en=_T)[0]
    assert fila["completada_en"] == "2026-09-30T13:23:00+00:00"


def test_numeros_que_vienen_como_texto():
    fila = filas_de_ventas(
        "lanny", [_nodo(itemPrice="28.99", qty=2, itemTotalCommission="1.7394")], vista_en=_T)[0]
    assert (fila["precio"], fila["cantidad"], fila["comision"]) == (28.99, 2, 1.7394)


def test_qty_ausente_vale_uno():
    assert filas_de_ventas("lanny", [_nodo(qty=None)], vista_en=_T)[0]["cantidad"] == 1


def test_model_id_ausente_vale_cero():
    assert filas_de_ventas("lanny", [_nodo(modelId=None)], vista_en=_T)[0]["model_id"] == 0


def test_referrer_vacio_queda_desconocido():
    assert filas_de_ventas("lanny", [_nodo(referrer=None)], vista_en=_T)[0]["origen"] == "desconocido"


def test_fechas_en_utc_iso():
    fila = filas_de_ventas("nick", [_nodo(purchaseTime=1790774580)], vista_en=_T)[0]
    assert fila["compra_en"] == "2026-09-30T13:23:00+00:00"
    assert fila["vista_en"] == "2026-10-02T00:00:00+00:00"


def test_resto_de_campos_del_item():
    fila = filas_de_ventas("nick", [_nodo()], vista_en=_T)[0]
    assert fila["estado"] == "PENDING"
    assert fila["producto"] == "Webcam"
    assert fila["imagen_url"] == "https://img/x"
    assert fila["categoria"] == "Informatica"


def test_setupjusto_va_a_la_cuenta_nick():
    assert filas_de_videos([_video(canal="setupjusto")])[0]["cuenta"] == "nick"


def test_lanny_va_a_la_cuenta_lanny():
    assert filas_de_videos([_video(canal="lanny")])[0]["cuenta"] == "lanny"


def test_video_sin_publicar_tiene_publicado_en_null():
    fila = filas_de_videos([_video(publicado_ts=None)])[0]
    assert fila["publicado_en"] is None
    assert fila["grabado_en"].startswith("2026-")


def test_video_publicado_tiene_fecha():
    fila = filas_de_videos([_video(publicado_ts=1790774580.0)])[0]
    assert fila["publicado_en"] == "2026-09-30T13:23:00+00:00"
