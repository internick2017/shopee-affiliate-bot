"""La factura mensual: que entra en la nota de Shopee y en la de cada tienda."""

from src.nota_fiscal import limites_del_mes, partes

OCT = limites_del_mes(2026, 10)
DIA_15 = OCT[0] + 14 * 86400


def _item(shopee, vendedor=0, tienda="T", estado="COMPLETED", cuando=DIA_15):
    return {"orders": [{"items": [{
        "completeTime": cuando, "displayItemStatus": estado, "shopName": tienda,
        "itemShopeeCommissionCapped": shopee, "itemSellerCommission": vendedor,
    }]}]}


def test_octubre_de_nick_da_la_factura_real():
    # Los 5 items que devolvio la API el 2026-11-03; la app pedia R$ 12,90 y R$ 6,66.
    nodos = [
        _item(0.99945, 6.663, "BuddyShopping"),
        _item(0, 0, "BuddyShopping", estado="CANCELLED"),
        _item(3.9528), _item(4.17), _item(3.7761),
    ]
    p = partes(nodos, *OCT)
    assert p.shopee == 12.90
    assert p.por_tienda == {"BuddyShopping": 6.66}
    assert p.total == 19.56


def test_fuera_del_mes_o_sin_completar_no_entra():
    nodos = [
        _item(5, cuando=OCT[1]),       # 1 de noviembre: va en la factura siguiente
        _item(5, cuando=OCT[0] - 1),   # 30 de septiembre
        _item(5, cuando=0),            # todavia no se completo
        _item(5, estado="PENDING"),
    ]
    assert partes(nodos, *OCT).shopee == 0


def test_limites_cruzan_el_anio():
    ini, fin = limites_del_mes(2026, 12)
    assert fin - ini == 31 * 86400
