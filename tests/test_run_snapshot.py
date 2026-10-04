"""La lectura de un nodo de productOfferV2, sin red ni base de datos."""

from run_snapshot import _a_muestra
from src.trend_store import Muestra


def test_convierte_un_nodo_completo():
    nodo = {"itemId": "123", "sales": 40, "productName": "Fone", "price": "59.90",
            "commissionRate": "0.12", "offerLink": "https://s.shopee.com.br/x"}
    assert _a_muestra(nodo) == Muestra(123, 40, titulo="Fone", precio=59.9,
                                       comision_pct=12.0, link="https://s.shopee.com.br/x")


def test_los_campos_que_faltan_o_vienen_vacios_quedan_en_cero():
    assert _a_muestra({"itemId": 7, "sales": None, "price": None}) == Muestra(7, 0)


def test_un_nodo_sin_item_o_con_datos_rotos_se_descarta():
    assert _a_muestra({"sales": 3}) is None
    assert _a_muestra({"itemId": "abc"}) is None
    assert _a_muestra({"itemId": 1, "price": "gratis"}) is None
