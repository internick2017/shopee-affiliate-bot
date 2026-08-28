import json
from decimal import Decimal

from src.product_ideas import (
    _PESO_VENTAS,
    _firma,
    retorno_por_venta,
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


def test_a_igual_retorno_gana_el_barato():
    """Sigue habiendo preferencia por la compra por impulso: con los mismos reales
    por venta, el mas barato convierte mas seguido."""
    barato = puntuar(comision_pct=40, ventas=100, rating=4.5, precio=25)   # R$10
    caro = puntuar(comision_pct=10, ventas=100, rating=4.5, precio=100)    # R$10
    assert barato > caro


def test_un_caro_rentable_le_gana_a_un_barato_pobre():
    """Corregido con las ventas reales de Nick: los items de R$80+ son el 8% de
    las ventas pero el 24% de la comision. La formula vieja los ponia en cero."""
    pobre = puntuar(comision_pct=8, ventas=1000, rating=4.5, precio=10)    # R$0,80
    rentable = puntuar(comision_pct=12, ventas=1000, rating=4.5, precio=120)  # R$14,40
    assert rentable > pobre


def test_el_factor_precio_nunca_es_cero():
    """La version anterior descartaba de plano todo lo de mas de R$80."""
    carisimo = puntuar(comision_pct=20, ventas=5000, rating=4.9, precio=5000)
    assert carisimo > 0.3


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


# --- variedad ---

def test_no_repite_el_mismo_producto():
    """El caso real: /ideas limpeza devolvia cinco Percarbonatos casi iguales."""
    nodos = [
        _nodo("Percarbonato 100% Puro Tira Manchas", comision="0.20"),
        _nodo("Percarbonato de Sodio 100% Puro Limpeza", comision="0.19"),
        _nodo("Percarbonato Puro 1kg Roupas", comision="0.18"),
        _nodo("Jogo de Lencol 400 Fios", comision="0.17"),
        _nodo("Fita Dupla Face Nano", comision="0.16"),
    ]
    r = buscar_ideas("limpeza", "a", "s", cuantas=3, http_post=_post(nodos))
    firmas = {_firma(i.titulo) for i in r}
    assert len(firmas) == 3
    assert "percarbonato" in firmas


def test_la_variedad_no_devuelve_de_menos():
    """Si no hay suficientes productos distintos, completa con los repetidos:
    devolver 2 cuando se pidieron 5 seria peor que devolver algo parecido."""
    nodos = [_nodo(f"Percarbonato variante {i}") for i in range(6)]
    assert len(buscar_ideas("limpeza", "a", "s", cuantas=5, http_post=_post(nodos))) == 5


def test_la_firma_ignora_palabras_de_relleno():
    assert _firma("Kit de 3 Pecas Organizador") == _firma("Organizador Multiuso Premium")


def test_el_mejor_puntaje_sigue_primero():
    """La variedad reordena descartando, no promoviendo: el numero uno no cambia."""
    nodos = [_nodo("Alfa", comision="0.02", ventas=10, precio="300"),
             _nodo("Beta", comision="0.25", ventas=9000, precio="25")]
    assert buscar_ideas("limpeza", "a", "s", http_post=_post(nodos))[0].titulo == "Beta"


def test_retorno_por_venta_es_precio_por_comision():
    assert retorno_por_venta(50.0, 10.0) == 5.0
    assert retorno_por_venta(0.0, 99.0) == 0.0


def test_excluye_los_ya_grabados():
    """Con 33 videos al mes, repetir un producto sin querer duele."""
    nodos = [_nodo("Alfa", comision="0.25"), _nodo("Beta", comision="0.20")]
    nodos[0]["itemId"] = 111
    nodos[1]["itemId"] = 222
    r = buscar_ideas("limpeza", "a", "s", excluir={111}, http_post=_post(nodos))
    assert [i.titulo for i in r] == ["Beta"]


def test_el_excluido_no_gasta_el_cupo_de_su_firma():
    """Se filtra ANTES de la variedad: si el descartado consumiera la firma,
    dejaria afuera al parecido que si sirve."""
    nodos = [_nodo("Percarbonato grabado", comision="0.25"),
             _nodo("Percarbonato disponible", comision="0.20")]
    nodos[0]["itemId"] = 111
    nodos[1]["itemId"] = 222
    r = buscar_ideas("limpeza", "a", "s", excluir={111}, http_post=_post(nodos))
    assert [i.titulo for i in r] == ["Percarbonato disponible"]


def test_todo_alias_tiene_nombre_y_viceversa():
    """Un alias sin nombre deja al bot diciendo 'Buscando en None'; un nombre sin
    alias es una categoria mapeada que nadie puede pedir."""
    from src.product_ideas import NOMBRES

    assert {c for c in CATEGORIAS.values() if c not in NOMBRES} == set()
    assert {c for c in NOMBRES if c not in CATEGORIAS.values()} == set()
