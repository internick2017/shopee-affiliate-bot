import json

from src.sales_report import resumen_ventas


class _Resp:
    def __init__(self, body):
        self.status_code = 200
        self._b = body
        self.text = json.dumps(body)

    def json(self):
        return self._b

    def close(self):
        pass


def _item(nombre="Producto", precio="25", comision="2.5", estado="COMPLETED"):
    return {"itemName": nombre, "itemPrice": precio, "qty": 1,
            "itemTotalCommission": comision, "displayItemStatus": estado}


def _post(items, capturar=None):
    def post(url, **kwargs):
        if capturar is not None:
            capturar.append(kwargs.get("data", ""))
        return _Resp({"data": {"conversionReport": {"nodes": [{"orders": [{"items": items}]}]}}})
    return post


def test_suma_solo_los_completados():
    """Contar los cancelados infla la comision con plata que no llego."""
    v = resumen_ventas("a", "s", http_post=_post([
        _item(comision="3"), _item(comision="99", estado="CANCELLED"),
        _item(comision="50", estado="PENDING"),
    ]))
    assert v.completados == 1
    assert v.cancelados == 1
    assert v.pendientes == 1
    assert v.comision == 3.0


def test_agrupa_por_banda_de_precio():
    v = resumen_ventas("a", "s", http_post=_post([
        _item(precio="10", comision="1"), _item(precio="30", comision="3"),
        _item(precio="200", comision="15"),
    ]))
    etiquetas = {b.etiqueta: b for b in v.bandas}
    assert etiquetas["hasta R$20"].items == 1
    assert etiquetas["R$20-50"].comision == 3.0
    assert etiquetas["mas de R$150"].por_item == 15.0


def test_comision_por_venta():
    v = resumen_ventas("a", "s", http_post=_post([
        _item(comision="4"), _item(comision="6")]))
    assert v.por_venta == 5.0


def test_sin_ventas_no_divide_por_cero():
    v = resumen_ventas("a", "s", http_post=_post([]))
    assert v.completados == 0
    assert v.por_venta == 0.0
    assert v.error is None


def test_top_ordenado_y_acumulado():
    v = resumen_ventas("a", "s", http_post=_post([
        _item("Barato", comision="1"), _item("Caro", comision="9"),
        _item("Barato", comision="1"),
    ]))
    assert v.top[0] == ("Caro", 9.0)
    assert v.top[1] == ("Barato", 2.0)


def test_la_ventana_de_dias_va_en_la_consulta():
    enviados = []
    resumen_ventas("a", "s", dias=7, ahora=1_000_000, http_post=_post([_item()], enviados))
    assert "purchaseTimeStart:395200" in enviados[0]
    assert "purchaseTimeEnd:1000000" in enviados[0]


def test_fallo_de_red_devuelve_error():
    def explota(url, **kwargs):
        raise OSError("sin red")
    v = resumen_ventas("a", "s", http_post=explota)
    assert v.error is not None


def test_precio_invalido_no_rompe():
    v = resumen_ventas("a", "s", http_post=_post([_item(precio="abc"), _item(comision="5")]))
    assert v.completados == 1
    assert v.comision == 5.0


def _post_nodos(nodos, capturar=None):
    """Varias conversiones, cada una con su `referrer`."""
    def post(url, **kwargs):
        if capturar is not None:
            capturar.append(kwargs.get("data", ""))
        return _Resp({"data": {"conversionReport": {"nodes": nodos}}})
    return post


def _nodo(referrer, items):
    return {"referrer": referrer, "orders": [{"items": items}]}


def test_separa_la_tasa_real_por_origen():
    """El motivo de todo esto: Shopee Video paga bastante menos que el link, y
    promediando los dos juntos no se ve."""
    v = resumen_ventas("a", "s", http_post=_post_nodos([
        _nodo("WhatsApp", [_item(precio="100", comision="8")]),
        _nodo("Shopeevideo-Shopee", [_item(precio="100", comision="4")]),
    ]))
    por = {o.etiqueta: o for o in v.origenes}
    assert por["WhatsApp"].tasa_pct == 8.0
    assert por["Shopee Video"].tasa_pct == 4.0


def test_origen_cuenta_las_unidades_no_las_lineas():
    """La tasa es comision sobre lo VENDIDO: 2 unidades de R$50 son R$100."""
    item = _item(precio="50", comision="10")
    item["qty"] = 2
    v = resumen_ventas("a", "s", http_post=_post_nodos([_nodo("WhatsApp", [item])]))
    o = v.origenes[0]
    assert o.vendido == 100.0
    assert o.tasa_pct == 10.0


def test_origen_ignora_los_no_completados():
    v = resumen_ventas("a", "s", http_post=_post_nodos([
        _nodo("WhatsApp", [_item(precio="100", comision="8"),
                           _item(precio="100", comision="99", estado="CANCELLED")]),
    ]))
    assert v.origenes[0].items == 1
    assert v.origenes[0].tasa_pct == 8.0


def test_origenes_ordenados_por_volumen_y_sin_referrer_no_rompe():
    v = resumen_ventas("a", "s", http_post=_post_nodos([
        _nodo(None, [_item(precio="10", comision="1")]),
        _nodo("WhatsApp", [_item(precio="10", comision="1"),
                           _item(precio="10", comision="1")]),
    ]))
    assert [o.etiqueta for o in v.origenes] == ["WhatsApp", "desconocido"]
