"""Subir a YouTube un video de Lanny ya producido, con su link y su comentario.

Decisiones de Nick (2026-10-29): el canal es "Lanny Herrera" de su cuenta de Google,
va de todo tipo (casa, ropa, belleza), sin sitio propio. Cada video lleva el link de
afiliado de la cuenta de Lanny con subIds ["youtube", "lanny"], para separar en el
panel de Shopee lo que vende YouTube; el link de Shopee Video no se reusa.

El link va en la descripcion y tambien como comentario del canal: el comentario es
lo primero que se ve en un Short. La API no deja fijarlo, eso queda a mano en Studio.

Todo lo que habla con afuera entra por parametro, para probar el flujo sin red.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .canal_youtube import CATEGORIA_ESTILO
from .grabados_store import PublicacionesStore, VideoProducido

CANAL = "lanny"
PLATAFORMA = "youtube"
TOKEN = "youtube_lanny_refresh"

AVISO = ("Este vídeo contém links de afiliado. Se você comprar por eles, "
         "recebo uma comissão, sem custo adicional para você.")


class NoSePublico(Exception):
    """El video no se subio: el mensaje dice por que y no quedo nada a medias."""


@dataclass
class Resultado:
    video_id: str
    link: str
    comentado: bool


def _sin_hashtags(texto: str) -> str:
    return re.sub(r"\s*#\S+", "", texto).strip()


def titulo(video: VideoProducido) -> str:
    """La primera frase de la legenda (sin hashtags) o, sin legenda, el titulo de
    Shopee. YouTube corta a 100 caracteres; el " #Shorts" entra siempre."""
    base = _sin_hashtags(video.legenda or "")
    base = re.split(r"(?<=[.!?])\s", base, maxsplit=1)[0].rstrip(".") if base else video.titulo
    return f"{base[:91].rstrip()} #Shorts"


def descripcion(video: VideoProducido, link: str) -> str:
    cuerpo = (video.legenda or video.titulo).strip()
    return f"{cuerpo}\n\nPara comprar, clique aqui: {link}\n\n{AVISO}"


def comentario(link: str) -> str:
    return f"Link do produto: {link}"


def resolver_archivo(video: VideoProducido, carpeta: Path) -> VideoProducido:
    """Muchas filas viejas guardan solo el nombre del mp4, sin la carpeta (202 de 207
    se encuentran asi, medido 2026-10-29). Si la ruta no existe, se busca el mismo
    nombre en `carpeta`; si tampoco esta, queda como estaba."""
    if video.archivo and not Path(video.archivo).is_file():
        candidato = carpeta / Path(video.archivo).name
        if candidato.is_file():
            video.archivo = str(candidato)
    return video


def pendientes(videos: list[VideoProducido], publicados: set[int]) -> list[VideoProducido]:
    """Los videos de Lanny con archivo en disco que todavia no estan en YouTube."""
    return [v for v in videos
            if v.item_id not in publicados and v.archivo and Path(v.archivo).is_file()]


def publicar(
    video: VideoProducido,
    store: PublicacionesStore,
    *,
    generar_link: Callable[[int], str],
    access_token: Callable[[], str | None],
    subir: Callable[..., str | None],
    comentar: Callable[[str, str, str], bool],
    privado: bool = False,
) -> Resultado:
    ya = store.id_externo(video.item_id, CANAL, PLATAFORMA)
    if ya:
        raise NoSePublico(f"Ya esta en YouTube: https://youtube.com/shorts/{ya}")
    if not video.archivo or not Path(video.archivo).is_file():
        raise NoSePublico(f"No encuentro el archivo: {video.archivo or '(vacio)'}")

    link = generar_link(video.item_id)
    token = access_token()
    if not token:
        raise NoSePublico("No se pudo renovar el acceso: corre 'autorizar' de nuevo")

    video_id = subir(video.archivo, titulo(video), descripcion(video, link), token,
                     privado=privado, categoria=CATEGORIA_ESTILO)
    if not video_id:
        raise NoSePublico("La subida fallo. No se guardo nada.")

    # Desde aca el video ya esta en YouTube: si guardar falla, el id no se pierde.
    try:
        store.registrar(video.item_id, canal=CANAL, plataforma=PLATAFORMA,
                        id_externo=video_id, link=link)
    except Exception as exc:  # noqa: BLE001 - se reporta con el comando de rescate
        raise NoSePublico(
            f"El video se subio ({video_id}) pero no se pudo guardar: {exc}\n"
            f"Asocialo con: youtube_lanny.py rescatar {video.item_id} {video_id} {link}"
        ) from exc
    return Resultado(video_id, link, comentar(video_id, comentario(link), token))
