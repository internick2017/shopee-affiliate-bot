import json
from datetime import UTC, datetime

import pytest

from src.grabados_store import VideoProducido
from src.panel_sync import (
    Supabase,
    filas_de_ventas,
    filas_de_videos,
    leer_conversiones,
    sincronizar,
)

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


# --- Lectura paginada, escritura en Supabase y sincronizacion (Task 3) ---

class _Resp:
    def __init__(self, body, status=200):
        self.status_code = status
        self._b = body
        self.text = json.dumps(body)

    def json(self):
        return self._b


def _pagina(nodos, siguiente=None):
    return {"data": {"conversionReport": {
        "nodes": nodos,
        "pageInfo": {"hasNextPage": siguiente is not None, "scrollId": siguiente or ""}}}}


def _shopee(paginas, consultas=None):
    """Doble del POST a Shopee: devuelve las paginas en orden. Una pagina None
    simula un fallo (HTTP 500)."""
    restantes = list(paginas)

    def post(url, *, data, headers):
        if consultas is not None:
            consultas.append(json.loads(data)["query"])
        p = restantes.pop(0)
        return _Resp({}, status=500) if p is None else _Resp(p)
    return post


class _FakeSupabase:
    def __init__(self, falla_en=None):
        self.upserts = []
        self.registros = []
        self._falla_en = falla_en

    def upsert(self, tabla, filas, conflicto):
        if tabla == self._falla_en:
            raise RuntimeError("supabase caido")
        self.upserts.append((tabla, filas, conflicto))

    def registrar(self, cuenta, empezo, ok, filas, error):
        self.registros.append({"cuenta": cuenta, "ok": ok, "filas": filas, "error": error})


class _FakeHttp:
    def __init__(self, status=201, body=""):
        self.status, self.body = status, body
        self.llamadas = []

    def post(self, url, *, json, headers, timeout):
        self.llamadas.append({"url": url, "json": json, "headers": headers})
        r = _Resp(None, status=self.status)
        r.text = self.body
        return r


def test_recorre_todas_las_paginas():
    consultas = []
    post = _shopee([_pagina([_nodo()], siguiente="abc"), _pagina([_nodo()])], consultas)
    nodos, error = leer_conversiones("a", "s", desde=0, hasta=1, http_post=post, pausa=0)
    assert len(nodos) == 2 and error is None
    assert "scrollId:" not in consultas[0]
    assert 'scrollId:"abc"' in consultas[1]


def test_pagina_que_falla_devuelve_lo_leido_y_el_error():
    post = _shopee([_pagina([_nodo()], siguiente="abc"), None])
    nodos, error = leer_conversiones("a", "s", desde=0, hasta=1, http_post=post, pausa=0)
    assert len(nodos) == 1
    assert error and "2" in error


def test_upsert_manda_merge_y_on_conflict():
    http = _FakeHttp()
    db = Supabase("https://x.supabase.co", "LLAVE-SECRETA", http=http)
    db.upsert("venta", [{"x": 1}], "cuenta,conversion_id,order_id,item_id,model_id")
    llamada = http.llamadas[0]
    assert llamada["url"] == ("https://x.supabase.co/rest/v1/venta"
                              "?on_conflict=cuenta,conversion_id,order_id,item_id,model_id")
    assert "resolution=merge-duplicates" in llamada["headers"]["Prefer"]
    assert llamada["json"] == [{"x": 1}]


def test_upsert_en_lotes_de_500():
    http = _FakeHttp()
    Supabase("https://x", "k", http=http).upsert("venta", [{"i": i} for i in range(1001)], "i")
    assert [len(c["json"]) for c in http.llamadas] == [500, 500, 1]


def test_upsert_sin_filas_no_llama():
    http = _FakeHttp()
    Supabase("https://x", "k", http=http).upsert("venta", [], "i")
    assert http.llamadas == []


def test_error_de_supabase_no_incluye_la_llave():
    http = _FakeHttp(status=401, body='{"message":"Invalid API key"}')
    db = Supabase("https://x", "LLAVE-SECRETA", http=http)
    with pytest.raises(RuntimeError) as e:
        db.upsert("venta", [{"x": 1}], "x")
    assert "401" in str(e.value)
    assert "LLAVE-SECRETA" not in str(e.value)


def test_registrar_escribe_en_sincronizacion():
    http = _FakeHttp()
    Supabase("https://x", "k", http=http).registrar("nick", _T, True, 3, None)
    llamada = http.llamadas[0]
    assert llamada["url"] == "https://x/rest/v1/sincronizacion"
    assert llamada["json"]["cuenta"] == "nick"
    assert llamada["json"]["ok"] is True and llamada["json"]["filas"] == 3


def test_una_cuenta_que_falla_no_frena_a_la_otra():
    post = _shopee([None, _pagina([_nodo()])])
    db = _FakeSupabase()
    r = sincronizar({"lanny": ("x", "y"), "nick": ("a", "b")}, [], db,
                    ahora=_T, http_post=post, pausa=0)
    assert r == {"lanny": False, "nick": True, "videos": True}
    assert db.registros[0]["cuenta"] == "lanny"
    assert db.registros[0]["ok"] is False and db.registros[0]["error"]
    assert db.registros[1] == {"cuenta": "nick", "ok": True, "filas": 1, "error": None}


def test_cuenta_sin_ventas_registra_ok_con_cero_filas():
    db = _FakeSupabase()
    r = sincronizar({"nick": ("a", "b")}, [], db, ahora=_T,
                    http_post=_shopee([_pagina([])]), pausa=0)
    assert r["nick"] is True
    assert db.registros[0] == {"cuenta": "nick", "ok": True, "filas": 0, "error": None}


def test_pagina_2_que_falla_escribe_lo_leido_y_marca_error():
    db = _FakeSupabase()
    post = _shopee([_pagina([_nodo()], siguiente="abc"), None])
    r = sincronizar({"nick": ("a", "b")}, [], db, ahora=_T, http_post=post, pausa=0)
    assert r["nick"] is False
    assert len(db.upserts[0][1]) == 1
    assert db.registros[0]["ok"] is False and db.registros[0]["filas"] == 1


def test_supabase_caido_marca_la_cuenta_con_error():
    db = _FakeSupabase(falla_en="venta")
    r = sincronizar({"nick": ("a", "b")}, [_video()], db, ahora=_T,
                    http_post=_shopee([_pagina([_nodo()])]), pausa=0)
    assert r == {"nick": False, "videos": True}
    assert "supabase caido" in db.registros[0]["error"]


def test_videos_se_copian_y_se_registran_sin_cuenta():
    db = _FakeSupabase()
    sincronizar({}, [_video(), _video(canal="lanny")], db, ahora=_T, pausa=0)
    tabla, filas, conflicto = db.upserts[0]
    assert (tabla, len(filas), conflicto) == ("video", 2, "canal,item_id")
    assert db.registros[0] == {"cuenta": None, "ok": True, "filas": 2, "error": None}


def test_ventana_de_90_dias():
    consultas = []
    sincronizar({"nick": ("a", "b")}, [], _FakeSupabase(), ahora=_T,
                http_post=_shopee([_pagina([])], consultas), pausa=0)
    fin = int(_T.timestamp())
    assert f"purchaseTimeStart:{fin - 90 * 86400}" in consultas[0]
    assert f"purchaseTimeEnd:{fin}" in consultas[0]
