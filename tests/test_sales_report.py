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
