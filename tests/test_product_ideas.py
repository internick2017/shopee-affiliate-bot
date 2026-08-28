import json
from decimal import Decimal

from src.product_ideas import (
    _PESO_VENTAS,
    CATEGORIAS,
    buscar_ideas,
    puntuar,
    resolver_categoria,
)


class _Resp:
    def __init__(self, body, status_code=200):
        self.status_code = status_code
        self._b = body
        self.text = json.dumps(body)

    def json(self):
        return self._b

    def close(self):
        pass


def _nodo(nombre, precio="20", ventas=1000, comision="0.10", rating="4.7", link="https://s.shopee.com.br/x"):
    return {"itemId": 1, "productName": nombre, "price": precio, "sales": ventas,
            "ratingStar": rating, "commissionRate": comision, "priceDiscountRate": 30,
            "imageUrl": "https://img", "offerLink": link, "shopName": "loja",
            "productCatIds": [100636]}


def _post(nodos, capturar=None):
    def post(url, **kwargs):
        if capturar is not None:
            capturar.append(kwargs.get("data", ""))
        return _Resp({"data": {"productOfferV2": {"nodes": nodos}}})
    return post


# --- puntaje ---

def test_comision_alta_gana_a_ventas_altas():
    """El criterio del canal: mejor pagar bien que ser el mas vendido."""
    saturado = puntuar(comision_pct=3, ventas=90000, rating=4.8, precio=20)
    rentable = puntuar(comision_pct=18, ventas=3000, rating=4.8, precio=20)
    assert rentable > saturado


def test_rating_bajo_no_suma():
    assert puntuar(comision_pct=10, ventas=100, rating=3.5, precio=20) == \
           puntuar(comision_pct=10, ventas=100, rating=4.0, precio=20)


def test_precio_caro_penaliza():
    barato = puntuar(comision_pct=10, ventas=100, rating=4.5, precio=25)
    caro = puntuar(comision_pct=10, ventas=100, rating=4.5, precio=300)
    assert barato > caro


def test_puntaje_esta_entre_0_y_1():
    assert 0 <= puntuar(comision_pct=0, ventas=0, rating=0, precio=9999) <= 1
    assert 0 <= puntuar(comision_pct=99, ventas=10**9, rating=5, precio=1) <= 1


def test_ventas_en_escala_log_no_aplastan():
    """Sin log, un exito masivo dominaria todos los demas factores."""
    p1 = puntuar(comision_pct=10, ventas=1000, rating=4.5, precio=20)
    p2 = puntuar(comision_pct=10, ventas=100000, rating=4.5, precio=20)
    # 100x mas ventas mueve el puntaje menos que el peso entero del factor.
    assert 0 < p2 - p1 < _PESO_VENTAS


# --- categorias ---

def test_resuelve_categoria_sin_acentos_ni_mayusculas():
    assert resolver_categoria("Calçados") == CATEGORIAS["calcados"]
    assert resolver_categoria("  LIMPEZA ") == CATEGORIAS["limpeza"]


def test_palabra_desconocida_no_es_categoria():
    assert resolver_categoria("organizador cozinha") is None


# --- busqueda ---

def test_categoria_usa_filtro_de_categoria():
    enviados = []
    buscar_ideas("limpeza", "a", "s", http_post=_post([_nodo("x")], enviados))
    assert "productCatId:100636" in enviados[0]
    assert "keyword" not in enviados[0]


def test_texto_libre_usa_keyword():
    enviados = []
    buscar_ideas("porta frios", "a", "s", http_post=_post([_nodo("x")], enviados))
    assert 'keyword:\\"porta frios\\"' in enviados[0] or 'keyword:"porta frios"' in enviados[0]


def test_devuelve_ordenado_por_puntaje():
    nodos = [_nodo("flojo", comision="0.02", ventas=10, rating="4.1", precio="200"),
             _nodo("bueno", comision="0.20", ventas=9000, rating="4.9", precio="19")]
    r = buscar_ideas("limpeza", "a", "s", http_post=_post(nodos))
    assert [i.titulo for i in r] == ["bueno", "flojo"]


def test_respeta_el_limite():
    nodos = [_nodo(f"p{i}") for i in range(10)]
    assert len(buscar_ideas("limpeza", "a", "s", cuantas=3, http_post=_post(nodos))) == 3


def test_descarta_nodos_incompletos():
    malo = _nodo("sin link"); malo["offerLink"] = None
    r = buscar_ideas("limpeza", "a", "s", http_post=_post([malo, _nodo("ok")]))
    assert [i.titulo for i in r] == ["ok"]


def test_texto_vacio_devuelve_vacio():
    assert buscar_ideas("   ", "a", "s", http_post=_post([_nodo("x")])) == []


def test_fallo_de_red_devuelve_vacio():
    def explota(url, **kwargs):
        raise OSError("sin red")
    assert buscar_ideas("limpeza", "a", "s", http_post=explota) == []


def test_convierte_comision_a_porcentaje():
    r = buscar_ideas("limpeza", "a", "s", http_post=_post([_nodo("x", comision="0.135")]))
    assert r[0].comision_pct == Decimal("13.500")
