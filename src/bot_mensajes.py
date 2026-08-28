"""Los mensajes que arma el bot generador, aparte de los handlers.

Viven acá y no dentro de `bot_generador.py` por una razón concreta: son lo único
de ese archivo que se puede probar sin levantar Telegram, y justamente ahí estaba
el bug del escapado. Como funciones puras (datos adentro, string afuera) cada
formato queda cubierto por un test.

Todo esto se manda con `parse_mode=HTML`, así que cualquier texto que venga de
afuera (títulos de producto de Shopee, nombres de tienda) tiene que pasar por
`esc()`. Los títulos traen "&" seguido ("Kit 2 & 3 peças") y Telegram rechaza el
mensaje ENTERO con "can't parse entities": el comando falla y no se ve por qué.
Las etiquetas <b>/<i> de las plantillas de acá NO se escapan, son nuestras.
"""

from __future__ import annotations

import html
from decimal import Decimal
from typing import Any, Iterable

from .post_builder import format_brl, rango_relevante


def esc(texto: Any) -> str:
    """Texto de afuera, listo para meter en HTML de Telegram."""
    return html.escape(str(texto)) if texto else ""


def brl(valor: Any) -> str:
    """Precio en formato brasileño: coma decimal y punto de miles.

    Envuelve a `format_brl`, el MISMO formateador que arma el post que se publica,
    para que el bot y el canal no muestren los precios distinto. Tolera floats, str
    y None porque acá los valores llegan de la API y del reporte de ventas, no
    siempre como Decimal.
    """
    try:
        return format_brl(Decimal(str(valor)))
    except (TypeError, ValueError, ArithmeticError):
        return format_brl(Decimal("0"))


def pct(valor: Any, decimales: int = 1) -> str:
    """Porcentaje con coma decimal, igual que los precios."""
    try:
        return f"{float(valor):.{decimales}f}".replace(".", ",") + "%"
    except (TypeError, ValueError):
        return "0,0%"


def texto_idea(n: int, idea: Any) -> str:
    aviso = aviso_rango(getattr(idea, "precio_min", None), getattr(idea, "precio_max", None))
    return (
        f"<b>{n}. {esc(idea.titulo[:90])}</b>\n"
        f"{brl(idea.precio)} - {idea.ventas} vendidos - "
        f"{idea.comision_pct:.0f}% comision - {idea.rating} estrellas\n"
        + (f"{aviso}\n" if aviso else "")
        + f"{idea.link}\n\n"
        f"<i>Referencia de video: /video {idea.link}</i>"
    )


def texto_tendencia(n: int, x: Any) -> str:
    return (
        f"<b>{n}. {esc(x.titulo[:80])}</b>\n"
        f"+{x.nuevas} ventas en {x.dias:.0f} dias "
        f"({x.por_dia:.0f}/dia, +{x.crecimiento_pct:.0f}%)\n"
        f"{x.ventas_antes} -> {x.ventas_ahora} | {brl(x.precio)} | "
        f"{x.comision_pct:.0f}% comision\n"
        f"{x.link}\n\n"
        f"<i>Referencia de video: /video {x.link} nativo</i>"
    )


def texto_grabados(total: int, ultimos: Iterable[Any]) -> str:
    lineas = [f"<b>{total} productos ya grabados</b>", ""]
    for g in ultimos:
        lineas.append(esc(g.titulo[:60]))
        lineas.append(f"  hace {g.dias_atras:.0f} dias - id {g.item_id}")
    lineas.append("")
    lineas.append("<i>Para volver a grabar uno: /olvidar_video (id)</i>")
    return "\n".join(lineas)


def texto_ventas(v: Any) -> str:
    lineas = [
        f"<b>Ultimos {v.dias} dias</b>",
        f"Comision: <b>{brl(v.comision)}</b> en {v.completados} ventas",
        f"Promedio por venta: {brl(v.por_venta)}",
    ]
    if v.cancelados or v.pendientes:
        lineas.append(f"({v.cancelados} canceladas, {v.pendientes} pendientes, no contadas)")

    if v.bandas:
        lineas.append("")
        lineas.append("<b>Por banda de precio</b>")
        for banda in v.bandas:
            lineas.append(
                f"{esc(banda.etiqueta)}: {banda.items} vendidos, "
                f"{brl(banda.comision)} ({brl(banda.por_item)} c/u)"
            )

    if v.origenes:
        lineas.append("")
        lineas.append("<b>Por origen del click</b>")
        for o in v.origenes:
            lineas.append(
                f"{esc(o.etiqueta)}: {o.items} vendidos, {pct(o.tasa_pct)} real "
                f"({brl(o.comision)})"
            )

    if v.top:
        lineas.append("")
        lineas.append("<b>Los que mas dejaron</b>")
        for nombre, com in v.top:
            lineas.append(f"{brl(com)} - {esc(nombre)}")
    return "\n".join(lineas)


def aviso_rango(minimo: Any, maximo: Any) -> str | None:
    """Advertencia de que el precio publicado es el de la variación más barata.

    Va SIEMPRE a Lanny, nunca dentro del post que se publica: el precio anunciado no
    esta mal (es el de partida, Shopee lo muestra igual), lo que falta es que ella lo
    sepa para aclararlo hablando en el video. Devuelve None si no vale la pena.
    """
    if not rango_relevante(minimo, maximo):
        return None
    lo, hi = Decimal(str(minimo)), Decimal(str(maximo))
    return (
        f"⚠️ Ojo: este producto tiene variaciones de {brl(lo)} a {brl(hi)}. "
        f"El precio del post es el de la <b>mas barata</b>; conviene aclararlo en el video."
    )
