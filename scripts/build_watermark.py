"""Genera `assets/watermark.png`: ícono de bolsa + rayo y el usuario de Shopee de
Lanny (@lannyherrera), en un PNG con fondo transparente, para pegarlo como marca
de agua sobre los videos verticales (ver `src/video_vertical.py`).

Se corre a mano cuando hay que regenerar el watermark (cambio de texto, tamaño,
etc.) — no en cada build. `python scripts/build_watermark.py`.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_SALIDA = Path(__file__).resolve().parent.parent / "assets" / "watermark.png"
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
    fuente = _fuente(22)
    texto = "@lannyherrera"

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
        "L",
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

    _SALIDA.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(_SALIDA)
    print(f"Guardado {_SALIDA} ({lienzo.width}x{lienzo.height})")


if __name__ == "__main__":
    main()
