from datetime import UTC, datetime

from src.panel_ideas import filas_de_ideas, subir_ideas
from src.panel_sync import Supabase

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
    assert db.orden == [("upsert", "ideia", 1, "item_id"),
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
