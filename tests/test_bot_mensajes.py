"""Los mensajes se mandan con parse_mode=HTML, y los titulos de Shopee traen "&"
("Kit 2 & 3 pecas") con frecuencia. Sin escapar, Telegram rechaza el mensaje ENTERO
con "can't parse entities" y el comando falla sin que se vea por que."""

from dataclasses import dataclass

from src.bot_mensajes import (
    esc,
    texto_grabados,
    texto_idea,
    texto_tendencia,
    texto_ventas,
)

TITULO_HOSTIL = 'Kit 2 & 3 pecas <b>oferta</b> "top"'


def test_esc_neutraliza_lo_que_rompe_el_parseo():
    assert esc("Kit 2 & 3") == "Kit 2 &amp; 3"
    assert esc("<b>hola</b>") == "&lt;b&gt;hola&lt;/b&gt;"
    assert esc(None) == ""


@dataclass
class _Idea:
    titulo: str = TITULO_HOSTIL
    precio: str = "19.90"
    ventas: int = 120
    comision_pct: float = 12.0
    rating: str = "4.9"
    link: str = "https://s.shopee.com.br/abc"


def test_idea_escapa_el_titulo_pero_deja_sus_propias_etiquetas():
    t = texto_idea(1, _Idea())
    assert "Kit 2 &amp; 3 pecas" in t
    assert "&lt;b&gt;oferta&lt;/b&gt;" in t
    assert t.startswith("<b>1. ")          # la negrita del template sobrevive
    assert "<b>oferta</b>" not in t        # la del titulo no


@dataclass
class _Tend:
    titulo: str = TITULO_HOSTIL
    nuevas: int = 40
    dias: float = 7.0
    por_dia: float = 5.7
    crecimiento_pct: float = 33.0
    ventas_antes: int = 120
    ventas_ahora: int = 160
    precio: float = 19.9
    comision_pct: float = 12.0
    link: str = "https://s.shopee.com.br/abc"


def test_tendencia_escapa_el_titulo():
    t = texto_tendencia(1, _Tend())
    assert "Kit 2 &amp; 3 pecas" in t
    assert "<b>oferta</b>" not in t


@dataclass
class _Grabado:
    item_id: int = 123
    titulo: str = TITULO_HOSTIL
    dias_atras: float = 3.0


def test_grabados_escapa_los_titulos():
    t = texto_grabados(1, [_Grabado()])
    assert "Kit 2 &amp; 3 pecas" in t
    assert "<b>oferta</b>" not in t
    assert "id 123" in t


@dataclass
class _Banda:
    etiqueta: str = "hasta R$20"
    items: int = 3
    comision: float = 6.0
    por_item: float = 2.0


@dataclass
class _Origen:
    etiqueta: str = "Shopee Video"
    items: int = 2
    comision: float = 2.82
    tasa_pct: float = 3.7


@dataclass
class _Ventas:
    dias: int = 90
    completados: int = 73
    cancelados: int = 14
    pendientes: int = 6
    comision: float = 236.86
    por_venta: float = 3.24
    bandas: tuple = (_Banda(),)
    origenes: tuple = (_Origen(),)
    top: tuple = ((TITULO_HOSTIL, 14.67),)


def test_ventas_escapa_los_nombres_de_producto():
    t = texto_ventas(_Ventas())
    assert "Kit 2 &amp; 3 pecas" in t
    assert "<b>oferta</b>" not in t


def test_ventas_muestra_los_bloques_reales():
    t = texto_ventas(_Ventas())
    assert "R$ 236,86</b> en 73 ventas" in t
    assert "(14 canceladas, 6 pendientes, no contadas)" in t
    assert "hasta R$20: 3 vendidos" in t
    assert "Shopee Video: 2 vendidos, 3,7% real" in t


def test_ventas_omite_los_bloques_vacios():
    t = texto_ventas(_Ventas(cancelados=0, pendientes=0, origenes=(), bandas=()))
    assert "no contadas" not in t
    assert "Por origen del click" not in t
    assert "Por banda de precio" not in t


from decimal import Decimal

from src.bot_mensajes import aviso_rango


def test_aviso_rango_calla_cuando_no_hay_variacion_relevante():
    """Suena en 1 de cada 3 productos; si avisara por centavos seria ruido y se
    dejaria de leer."""
    assert aviso_rango(Decimal("20"), Decimal("20")) is None
    assert aviso_rango(Decimal("20"), Decimal("25")) is None      # x1.25
    assert aviso_rango(Decimal("20"), None) is None
    assert aviso_rango(None, Decimal("60")) is None
    assert aviso_rango(Decimal("0"), Decimal("60")) is None       # no dividir por cero


def test_aviso_rango_avisa_desde_una_vez_y_media():
    assert aviso_rango(Decimal("20"), Decimal("30")) is not None  # x1.5 justo
    t = aviso_rango(Decimal("9.88"), Decimal("69.88"))            # el caso real peor
    assert "R$ 9,88" in t and "R$ 69,88" in t


def test_aviso_rango_dice_que_el_precio_publicado_es_el_mas_barato():
    """Es EL punto del aviso: `price` es siempre el minimo, medido en 300 de 300."""
    t = aviso_rango(Decimal("15.98"), Decimal("69.99"))
    assert "mas barata" in t.lower() or "barata" in t.lower()


from src.bot_mensajes import brl


def test_brl_usa_el_formato_brasileno():
    """Coma decimal y punto de miles. Reusa format_brl, el mismo que arma el post."""
    assert brl("16.9") == "R$ 16,90"
    assert brl(236.86) == "R$ 236,86"
    assert brl(Decimal("1234.5")) == "R$ 1.234,50"
    assert brl(0) == "R$ 0,00"


def test_brl_no_rompe_con_basura():
    assert brl(None) == "R$ 0,00"
    assert brl("no es un numero") == "R$ 0,00"


def test_los_mensajes_no_muestran_punto_decimal():
    """El sintoma que se reporto: "R$ 16.9" en vez de "R$ 16,90"."""
    t = texto_ventas(_Ventas())
    assert "R$ 236,86" in t
    assert "R$ 236.86" not in t
    a = aviso_rango(Decimal("16.9"), Decimal("49.9"))
    assert "R$ 16,90" in a and "R$ 49,90" in a


from src.bot_mensajes import pct


def test_pct_usa_coma_decimal():
    """Ni portugues ni español escriben "7.6%"."""
    assert pct(7.6) == "7,6%"
    assert pct(3.7) == "3,7%"
    assert pct(0) == "0,0%"


def test_ventas_muestra_los_porcentajes_con_coma():
    t = texto_ventas(_Ventas())
    assert "3,7% real" in t
    assert "3.7%" not in t
