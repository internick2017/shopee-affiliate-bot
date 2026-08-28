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
from typing import Any, Iterable


def esc(texto: Any) -> str:
    """Texto de afuera, listo para meter en HTML de Telegram."""
    return html.escape(str(texto)) if texto else ""


def texto_idea(n: int, idea: Any) -> str:
    return (
        f"<b>{n}. {esc(idea.titulo[:90])}</b>\n"
        f"R$ {idea.precio} - {idea.ventas} vendidos - "
        f"{idea.comision_pct:.0f}% comision - {idea.rating} estrellas\n"
        f"{idea.link}\n\n"
        f"<i>Referencia de video: /video {idea.link}</i>"
    )


def texto_tendencia(n: int, x: Any) -> str:
    return (
        f"<b>{n}. {esc(x.titulo[:80])}</b>\n"
        f"+{x.nuevas} ventas en {x.dias:.0f} dias "
        f"({x.por_dia:.0f}/dia, +{x.crecimiento_pct:.0f}%)\n"
        f"{x.ventas_antes} -> {x.ventas_ahora} | R$ {x.precio:.2f} | "
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
        f"Comision: <b>R$ {v.comision:.2f}</b> en {v.completados} ventas",
        f"Promedio por venta: R$ {v.por_venta:.2f}",
    ]
    if v.cancelados or v.pendientes:
        lineas.append(f"({v.cancelados} canceladas, {v.pendientes} pendientes, no contadas)")

    if v.bandas:
        lineas.append("")
        lineas.append("<b>Por banda de precio</b>")
        for banda in v.bandas:
            lineas.append(
                f"{esc(banda.etiqueta)}: {banda.items} vendidos, "
                f"R$ {banda.comision:.2f} (R$ {banda.por_item:.2f} c/u)"
            )

    if v.origenes:
        lineas.append("")
        lineas.append("<b>Por origen del click</b>")
        for o in v.origenes:
            lineas.append(
                f"{esc(o.etiqueta)}: {o.items} vendidos, {o.tasa_pct:.1f}% real "
                f"(R$ {o.comision:.2f})"
            )

    if v.top:
        lineas.append("")
        lineas.append("<b>Los que mas dejaron</b>")
        for nombre, com in v.top:
            lineas.append(f"R$ {com:.2f} - {esc(nombre)}")
    return "\n".join(lineas)
