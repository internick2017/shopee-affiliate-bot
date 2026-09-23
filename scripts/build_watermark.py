"""Genera un PNG de marca de agua: ícono de bolsa + rayo y un usuario de Shopee,
con fondo transparente, para pegarlo sobre los videos verticales (ver
`src/video_vertical.py`).

Sin argumentos genera el de siempre, `assets/watermark.png` con "lannyherrera", que
es el que usa el bot al publicar para Lanny. Con `--usuario` y `--salida` genera
cualquier otro: Nick publica también en un canal propio y necesita el suyo.

IMPORTANTE (2026-09-08): el texto va SIN arroba. Shopee removió un video con
"@lannyherrera" en la marca de agua y restringió la cuenta, citando su política contra
"direcionar os usuários" hacia plataformas competidoras — el símbolo @ es la señal más
obvia de que es un handle de otra red social. Sacarlo es una mitigación, no una
solución confirmada (ver memoria global
shopee-video-flow-video-removido-restriccion-cuenta.md). No volver a poner el @ sin
haber confirmado antes que el problema no vuelve a aparecer.

Se corre a mano cuando hay que regenerar un watermark, no en cada build:

    python scripts/build_watermark.py
    python scripts/build_watermark.py --usuario nickgranados --salida assets/watermark-nick.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_RAIZ = Path(__file__).resolve().parent.parent
_SALIDA = _RAIZ / "assets" / "watermark.png"
_USUARIO = "lannyherrera"
_ALTO = 60
_PAD = 10
_RADIO_ICONO = 8
_COLOR_TEXTO = (255, 255, 255, 255)
_COLOR_ICONO_FONDO = (255, 61, 110, 255)
_COLOR_ICONO_TEXTO = (255, 255, 255, 255)


def _fuente(tam: int) -> ImageFont.FreeTypeFont:
    for nombre in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usuario", default=_USUARIO, help="usuario de Shopee, SIN arroba")
    p.add_argument("--salida", type=Path, default=_SALIDA)
    args = p.parse_args()

    fuente = _fuente(22)
    texto = args.usuario
    # La letra del ícono sale del propio usuario, así no hay que tocar el código
    # para cada marca nueva. Con @lannyherrera da "L", igual que la versión fija
    # que había antes.
    inicial = texto.lstrip("@")[:1].upper() or "?"
    salida = args.salida if args.salida.is_absolute() else _RAIZ / args.salida

    tmp = Image.new("RGBA", (1, 1))
    medidas = ImageDraw.Draw(tmp).textbbox((0, 0), texto, font=fuente)
    ancho_texto = medidas[2] - medidas[0]

    icono_lado = _ALTO - 2 * _PAD
    ancho = _PAD + icono_lado + 8 + ancho_texto + _PAD
    lienzo = Image.new("RGBA", (ancho, _ALTO), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lienzo)

    draw.rounded_rectangle(
        (_PAD, _PAD, _PAD + icono_lado, _PAD + icono_lado),
        radius=_RADIO_ICONO,
        fill=_COLOR_ICONO_FONDO,
    )
    fuente_icono = _fuente(round(icono_lado * 0.65))
    draw.text(
        (_PAD + icono_lado / 2, _PAD + icono_lado / 2),
        inicial,
        font=fuente_icono,
        fill=_COLOR_ICONO_TEXTO,
        anchor="mm",
    )

    draw.text(
        (_PAD + icono_lado + 8, _ALTO / 2),
        texto,
        font=fuente,
        fill=_COLOR_TEXTO,
        anchor="lm",
    )

    salida.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(salida)
    print(f"Guardado {salida} ({lienzo.width}x{lienzo.height})")


if __name__ == "__main__":
    main()
