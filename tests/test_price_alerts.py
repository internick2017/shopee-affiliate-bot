import pytest

from src.price_alerts import (
    Caida,
    avisar_caidas,
    detectar_caidas,
    enviar_telegram,
    texto_alerta,
)
from src.trend_store import TrendStore

_DIA = 86400
_HOY = 20_000 * _DIA + 3600


def _nodo(item_id=1, price="50", **campos):
    base = {"itemId": item_id, "productName": f"Produto {item_id}", "price": price,
            "commissionRate": "0.10", "offerLink": f"https://s.shopee.com.br/{item_id}",
            "imageUrl": "https://img/x"}
    base.update(campos)
    return base


def test_detecta_una_caida_fuerte_contra_la_referencia():
    [c] = detectar_caidas([_nodo(1, price="50")], {1: 100.0})
    assert (c.item_id, c.precio_antes, c.precio_ahora) == (1, 100.0, 50.0)
    assert c.pct == 50.0


def test_una_baja_chica_no_es_alerta():
    assert detectar_caidas([_nodo(1, price="80")], {1: 100.0}) == []


def test_sin_referencia_no_hay_alerta():
    """Un producto que aparece hoy por primera vez no tiene contra que compararse."""
    assert detectar_caidas([_nodo(1, price="5")], {}) == []


def test_un_producto_barato_no_alerta():
    """De R$8 a R$4 es 50%, pero no es una oportunidad: es ruido."""
    assert detectar_caidas([_nodo(1, price="4")], {1: 8.0}) == []


def test_precio_cero_o_roto_se_ignora():
    assert detectar_caidas([_nodo(1, price="0"), _nodo(2, price=None)], {1: 100.0, 2: 100.0}) == []


def test_ordena_por_la_caida_mas_grande():
    nodos = [_nodo(1, price="55"), _nodo(2, price="20")]
    assert [c.item_id for c in detectar_caidas(nodos, {1: 100.0, 2: 100.0})] == [2, 1]


def test_el_texto_dice_antes_ahora_y_el_link():
    c = Caida(item_id=1, titulo="Fone Bluetooth", precio_antes=100.0, precio_ahora=40.0,
              comision_pct=10.0, link="https://s.shopee.com.br/1")
    t = texto_alerta(c)
    assert "Fone Bluetooth" in t
    assert "R$ 100,00" in t and "R$ 40,00" in t and "-60%" in t
    assert "https://s.shopee.com.br/1" in t


class _Http:
    def __init__(self, status=200):
        self.status, self.llamadas = status, []

    def post(self, url, *, json, timeout):
        self.llamadas.append((url, json))

        class _R:
            status_code = self.status
            text = "Bad Request: chat not found"
        return _R()


def test_enviar_telegram_manda_al_chat():
    http = _Http()
    enviar_telegram("TOKEN", 123, "hola", http=http)
    [(url, cuerpo)] = http.llamadas
    assert url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert cuerpo["chat_id"] == 123 and cuerpo["text"] == "hola"


def test_enviar_telegram_falla_sin_mostrar_el_token():
    with pytest.raises(RuntimeError) as e:
        enviar_telegram("SECRETO", 123, "hola", http=_Http(status=400))
    assert "SECRETO" not in str(e.value)
    assert "chat not found" in str(e.value)


@pytest.fixture
def store(tmp_path):
    return TrendStore(tmp_path / "t.db")


def test_referencia_es_la_mediana_de_los_dias_previos(store):
    for dias_atras, precio in ((3, 100), (2, 90), (1, 110)):
        store.registrar(1, 10, precio=precio, now=_HOY - dias_atras * _DIA)
    store.registrar(1, 10, precio=40, now=_HOY)
    assert store.precios_de_referencia(now=_HOY) == {1: 100.0}


def test_referencia_pide_un_minimo_de_dias(store):
    """Con uno o dos dias no se sabe cual es el precio normal."""
    store.registrar(1, 10, precio=100, now=_HOY - _DIA)
    store.registrar(1, 10, precio=100, now=_HOY - 2 * _DIA)
    assert store.precios_de_referencia(now=_HOY) == {}


def test_referencia_ignora_lo_que_quedo_fuera_de_la_ventana(store):
    for dias_atras in (40, 41, 42):
        store.registrar(1, 10, precio=100, now=_HOY - dias_atras * _DIA)
    assert store.precios_de_referencia(now=_HOY) == {}


def test_un_producto_se_alerta_una_sola_vez_por_dia(store):
    assert store.marcar_alertado(1, now=_HOY) is True
    assert store.marcar_alertado(1, now=_HOY + 3600) is False
    assert store.marcar_alertado(1, now=_HOY + _DIA) is True


def _caida(item_id=1):
    return Caida(item_id=item_id, titulo="Fone", precio_antes=100.0, precio_ahora=50.0,
                 comision_pct=10.0, link="https://s.shopee.com.br/x")


def test_avisa_cada_caida_una_sola_vez_por_dia(store):
    enviados = []
    assert avisar_caidas([_caida(1), _caida(2)], store, enviados.append, now=_HOY) == 2
    assert avisar_caidas([_caida(1), _caida(2)], store, enviados.append, now=_HOY + 3600) == 0
    assert len(enviados) == 2


def test_si_el_envio_falla_la_caida_se_reintenta_en_la_corrida_siguiente(store):
    def sin_red(_texto):
        raise ConnectionError("sin red")

    enviados = []
    assert avisar_caidas([_caida()], store, sin_red, now=_HOY) == 0
    assert avisar_caidas([_caida()], store, enviados.append, now=_HOY + 3600) == 1
    assert enviados == [texto_alerta(_caida())]


def test_un_envio_que_falla_no_frena_los_demas(store):
    enviados = []

    def falla_el_primero(texto):
        if not enviados:
            enviados.append(None)
            raise ConnectionError("sin red")
        enviados.append(texto)

    assert avisar_caidas([_caida(1), _caida(2)], store, falla_el_primero, now=_HOY) == 1
