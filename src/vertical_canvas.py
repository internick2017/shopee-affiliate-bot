"""Convierte la foto cuadrada de un producto en un lienzo vertical 9:16 listo para
usar como imagen de referencia en un generador de video (Gemini/Veo) apuntando a
Shopee Video.

El porqué: las fotos que devuelve la API de Shopee (`imageUrl` de `productOfferV2`)
son SIEMPRE cuadradas — medido sobre productos reales: 1024x1024, 900x900, 800x800.
Darle una imagen 1:1 a un modelo image-to-video y pedirle 9:16 por texto lo obliga a
inventar el 44% de alto que falta, y el contexto vertical más obvio para una imagen
cuadrada es la pantalla de un celular: de ahí los mockups de teléfono y los laterales
desenfocados. La instrucción de texto compite contra la geometría de la imagen, y la
geometría gana. Así que el formato se resuelve ANTES, en el insumo, no en el prompt.

El relleno de arriba y abajo se genera de la propia foto (recorte que cubre el alto,
desenfocado y oscurecido) en vez de barras negras o color plano: le da al modelo
contenido vertical coherente para animar. La foto se pega a ancho completo y se
funde con el fondo mediante un degradado de opacidad arriba y abajo — sin ese
fundido se ve el rectángulo pegado y la referencia parece un collage, que es
exactamente la pista que lleva al modelo a componer "una imagen dentro de otra".

Zona segura: la interfaz de Shopee Video ocupa arriba y abajo del cuadro, así que el
producto se centra en una banda central y nunca se acerca a los extremos.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_ANCHO = 1080
_ALTO = 1920
# Fracción del alto reservada a la interfaz de Shopee Video (arriba y abajo).
_MARGEN_SUPERIOR = 0.15
_MARGEN_INFERIOR = 0.22
# Cuánto del ancho puede ocupar el producto como máximo.
_ANCHO_MAX_PRODUCTO = 1.0
_DESENFOQUE = 110
_OSCURECIDO = 0.70
# Alto del degradado que funde la foto con el fondo, en píxeles. Corto (90) deja
# ver el corte; 190 da una transición que no se lee como borde.
_FUNDIDO = 190


def _fondo(im, ancho: int, alto: int):
    """Fondo del lienzo: la foto extendida por espejo hasta cubrir ancho x alto,
    después desenfocada, desaturada y oscurecida.

    El espejo en vez del recorte central ampliado: ampliar el centro de la foto
    hasta cubrir 1920 de alto agranda objetos concretos y reconocibles, y el
    resultado se lee como "otra foto atrás". El espejo continúa el borde, que es
    justo la zona que toca el producto, así que el relleno queda como una
    prolongación de la misma superficie."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    w, h = im.size
    escala = ancho / w
    base = im.resize((ancho, max(1, round(h * escala))), Image.LANCZOS)
    bw, bh = base.size
    lienzo = Image.new("RGB", (ancho, alto))
    # Mosaico espejado vertical: la fila i alterna original / volteada.
    y = (alto - bh) // 2
    volteada = ImageOps.flip(base)
    fila = 0
    while y > 0:
        y -= bh
        fila += 1
    while y < alto:
        lienzo.paste(volteada if fila % 2 else base, (0, y))
        y += bh
        fila += 1
    borroso = lienzo.filter(ImageFilter.GaussianBlur(_DESENFOQUE))
    apagado = ImageEnhance.Color(borroso).enhance(0.6)
    return ImageEnhance.Brightness(apagado).enhance(_OSCURECIDO)


def _medidas_producto(w: int, h: int, ancho: int, alto: int) -> tuple[int, int, int, int]:
    """Tamaño y posición del producto dentro de la zona segura central.

    Devuelve (nuevo_ancho, nuevo_alto, x, y). El producto entra COMPLETO (contain,
    no cover): recortarlo sería justamente el error que este módulo evita."""
    ancho_disp = ancho * _ANCHO_MAX_PRODUCTO
    alto_disp = alto * (1 - _MARGEN_SUPERIOR - _MARGEN_INFERIOR)
    escala = min(ancho_disp / w, alto_disp / h)
    nw, nh = max(1, round(w * escala)), max(1, round(h * escala))
    x = (ancho - nw) // 2
    # Centrado dentro de la banda segura, no del lienzo entero.
    banda_arriba = alto * _MARGEN_SUPERIOR
    y = round(banda_arriba + (alto_disp - nh) / 2)
    return nw, nh, x, y


def _mascara_fundido(ancho: int, alto: int):
    """Máscara de opacidad: opaca en el centro, con degradado a transparente en el
    borde superior e inferior para que la foto se funda con el fondo desenfocado."""
    from PIL import Image

    mascara = Image.new("L", (ancho, alto), 255)
    px = mascara.load()
    fundido = min(_FUNDIDO, alto // 3)
    for i in range(fundido):
        valor = round(255 * (i / fundido))
        for x in range(ancho):
            px[x, i] = valor
            px[x, alto - 1 - i] = valor
    return mascara


def build_vertical_canvas(image_bytes: bytes, *, ancho: int = _ANCHO, alto: int = _ALTO) -> bytes:
    """Devuelve un JPEG `ancho` x `alto` (default 1080x1920) con el producto
    centrado en la zona segura sobre un fondo desenfocado derivado de la foto.

    Ante cualquier fallo devuelve los bytes originales: el llamador siempre tiene
    algo que mostrar, aunque no esté en formato vertical."""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        lienzo = _fondo(im, ancho, alto)
        nw, nh, x, y = _medidas_producto(*im.size, ancho, alto)
        producto = im.resize((nw, nh), Image.LANCZOS)
        lienzo.paste(producto, (x, y), _mascara_fundido(nw, nh))
        out = io.BytesIO()
        lienzo.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception:
        logger.warning("No se pudo armar el lienzo vertical", exc_info=True)
        return image_bytes
