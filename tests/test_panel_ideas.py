from datetime import UTC, datetime

from src.panel_ideas import filas_de_ideas, filas_em_alta, subir_ideas
from src.panel_sync import Supabase
from src.trend_store import Tendencia

_T = datetime(2026, 10, 3, 12, tzinfo=UTC)
_CASA = 100636


def _nodo(item_id=1, **campos):
    base = {"itemId": item_id, "productName": f"Produto {item_id}", "price": "40",
            "priceMin": "40", "priceMax": "60", "sales": 1000, "ratingStar": "4.8",
            "commissionRate": "0.10", "priceDiscountRate": 20,
            "imageUrl": "https://img/x", "offerLink": "https://s.shopee.com.br/afiliado",
            "productLink": f"https://shopee.com.br/product/9/{item_id}"}
    base.update(campos)
    return base


def test_una_fila_por_producto_con_su_categoria():
    [fila] = filas_de_ideas({_CASA: [_nodo(7)]}, {}, vista_en=_T)
    assert fila["item_id"] == 7
    assert fila["categoria_id"] == _CASA
    assert fila["categoria"] == "Casa e Cozinha"
    assert fila["titulo"] == "Produto 7"
    assert fila["precio"] == 40.0
    assert fila["comision_pct"] == 10.0
    assert fila["ventas"] == 1000
    assert fila["descuento_pct"] == 20
    assert fila["vista_en"] == "2026-10-03T12:00:00+00:00"
    assert 0 < fila["puntaje"] <= 1
    assert fila["tipo"] == "mais_vendidos"
    assert fila["ventas_recentes"] is None


def test_el_link_es_el_del_producto_no_el_de_afiliado():
    """El panel lo ven dos cuentas: un link ya monetizado con una serviria solo a ella."""
    [fila] = filas_de_ideas({_CASA: [_nodo(7)]}, {}, vista_en=_T)
    assert fila["link"] == "https://shopee.com.br/product/9/7"


def test_sin_link_de_producto_usa_el_de_oferta():
    [fila] = filas_de_ideas({_CASA: [_nodo(7, productLink=None)]}, {}, vista_en=_T)
    assert fila["link"] == "https://s.shopee.com.br/afiliado"


def test_se_queda_con_las_mejores_de_cada_categoria():
    nodos = [_nodo(1, productName="Garrafa termica", sales=10),
             _nodo(2, productName="Mop giratorio", sales=50000),
             _nodo(3, productName="Luminaria de mesa", sales=900)]
    filas = filas_de_ideas({_CASA: nodos}, {}, vista_en=_T, por_categoria=2)
    assert [f["item_id"] for f in filas] == [2, 3]


def test_un_nodo_sin_nombre_no_entra():
    assert filas_de_ideas({_CASA: [_nodo(1, productName="")]}, {}, vista_en=_T) == []


def test_ventas_por_dia_sale_de_la_tendencia():
    filas = filas_de_ideas({_CASA: [_nodo(1, productName="Mop"), _nodo(2, productName="Balde")]},
                           {1: 12.5}, vista_en=_T)
    por_id = {f["item_id"]: f["ventas_por_dia"] for f in filas}
    assert por_id == {1: 12.5, 2: None}


def _reciente(item_id, nuevas, ventas_ahora=1000, dias=10.0):
    return Tendencia(item_id=item_id, titulo="", ventas_antes=ventas_ahora - nuevas,
                     ventas_ahora=ventas_ahora, dias=dias, precio=0, comision_pct=0, link="")


def _categoria_con(*candidatos):
    """Los candidatos mas tres productos muy vendidos, que dejan la mediana en 50.000."""
    grandes = [_nodo(900 + i, productName=f"Campeao {i}", sales=50000 + i) for i in range(3)]
    return {_CASA: [*candidatos, *grandes]}


def test_em_alta_entra_el_poco_vendido_que_vende_ahora():
    [fila] = filas_em_alta(_categoria_con(_nodo(1, sales=1000)),
                           {1: _reciente(1, nuevas=400)}, vista_en=_T)
    assert fila["item_id"] == 1
    assert fila["tipo"] == "em_alta"
    assert fila["ventas_recentes"] == 400
    assert fila["ventas_por_dia"] == 40.0
    assert fila["puntaje"] == 0.4          # 400 de sus 1.000 ventas son recientes
    assert fila["link"] == "https://shopee.com.br/product/9/1"


def test_em_alta_deja_afuera_al_que_vendio_mas_que_la_mitad_de_su_categoria():
    nodos = _categoria_con(_nodo(1, sales=1000))
    recientes = {902: _reciente(902, nuevas=5000, ventas_ahora=50002)}
    assert filas_em_alta(nodos, recientes, vista_en=_T) == []


def test_em_alta_exige_treinta_ventas_recientes():
    nodos = _categoria_con(_nodo(1, sales=1000), _nodo(2, productName="Balde", sales=1000))
    recientes = {1: _reciente(1, nuevas=29), 2: _reciente(2, nuevas=30)}
    assert [f["item_id"] for f in filas_em_alta(nodos, recientes, vista_en=_T)] == [2]


def test_em_alta_sin_historial_no_entra():
    assert filas_em_alta(_categoria_con(_nodo(1, sales=1000)), {}, vista_en=_T) == []


def test_em_alta_exige_buena_calificacion():
    nodos = _categoria_con(_nodo(1, sales=1000, ratingStar="4.6"),
                           _nodo(2, productName="Balde", sales=1000, ratingStar="4.7"))
    recientes = {1: _reciente(1, nuevas=400), 2: _reciente(2, nuevas=400)}
    assert [f["item_id"] for f in filas_em_alta(nodos, recientes, vista_en=_T)] == [2]


def test_em_alta_exige_un_real_por_venta():
    nodos = _categoria_con(_nodo(1, sales=1000, price="9", commissionRate="0.10"),
                           _nodo(2, productName="Balde", sales=1000, price="10",
                                 commissionRate="0.10"))
    recientes = {1: _reciente(1, nuevas=400), 2: _reciente(2, nuevas=400)}
    assert [f["item_id"] for f in filas_em_alta(nodos, recientes, vista_en=_T)] == [2]


def test_em_alta_ordena_por_la_parte_de_sus_ventas_que_es_reciente():
    nodos = _categoria_con(_nodo(1, productName="Mop", sales=3000),
                           _nodo(2, productName="Balde", sales=40))
    recientes = {1: _reciente(1, nuevas=1500, ventas_ahora=3000),
                 2: _reciente(2, nuevas=38, ventas_ahora=40)}
    assert [f["item_id"] for f in filas_em_alta(nodos, recientes, vista_en=_T)] == [2, 1]


def test_em_alta_no_rellena_cuando_pocos_cumplen():
    nodos = _categoria_con(_nodo(1, productName="Mop", sales=1000),
                           _nodo(2, productName="Balde", sales=1000))
    assert len(filas_em_alta(nodos, {1: _reciente(1, nuevas=400)}, vista_en=_T)) == 1


def test_em_alta_respeta_el_tope_por_categoria():
    candidatos = [_nodo(i, productName=f"Coisa{i} nova", sales=1000) for i in range(1, 4)]
    recientes = {i: _reciente(i, nuevas=100 * i) for i in range(1, 4)}
    filas = filas_em_alta(_categoria_con(*candidatos), recientes, vista_en=_T, por_categoria=2)
    assert [f["item_id"] for f in filas] == [3, 2]


class _Db:
    def __init__(self):
        self.orden = []

    def upsert(self, tabla, filas, conflicto):
        self.orden.append(("upsert", tabla, len(filas), conflicto))

    def borrar_anteriores(self, tabla, columna, limite):
        self.orden.append(("borrar_anteriores", tabla, columna, limite))


def test_subir_ideas_sube_y_despues_borra_las_viejas():
    db = _Db()
    filas = filas_de_ideas({_CASA: [_nodo(1)]}, {}, vista_en=_T)
    assert subir_ideas(db, filas, vista_en=_T) == 1
    assert db.orden == [("upsert", "ideia", 1, "item_id,tipo"),
                        ("borrar_anteriores", "ideia", "vista_en", "2026-10-03T12:00:00+00:00")]


def test_subir_ideas_sin_filas_no_vacia_el_panel():
    """Si la API de Shopee fallo y no hay ideas, las de ayer siguen sirviendo."""
    db = _Db()
    assert subir_ideas(db, [], vista_en=_T) == 0
    assert db.orden == []


class _Http:
    def __init__(self):
        self.llamadas = []

    def delete(self, url, *, headers, timeout, params=None):
        self.llamadas.append((url, params))

        class _R:
            status_code = 204
            text = ""
        return _R()


def test_borrar_anteriores_filtra_por_menor_que():
    http = _Http()
    Supabase("https://x.supabase.co", "llave", http=http).borrar_anteriores(
        "ideia", "vista_en", "2026-10-03T12:00:00+00:00")
    assert http.llamadas == [("https://x.supabase.co/rest/v1/ideia",
                              {"vista_en": "lt.2026-10-03T12:00:00+00:00"})]
