"""Adaptador de YouTube: autorizar, subir un Short y comentar.

Copia recortada de `sync/canales/youtube.py` del repo home-office-br (Setup Justo),
donde ya subio mas de 40 Shorts. Se copia y no se importa para que el bot no
dependa de otro repo. Si se arregla un bug en uno, revisar el otro. El cliente
HTTP entra por parametro para inyectar un doble en los tests, y cualquier fallo
de red devuelve None (o False) en vez de romper.

A diferencia de Mercado Livre, Google no rota el refresh token en cada
renovación: `renovar_token` devuelve solo el access token.
"""

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
# force-ssl y no upload: además de subir, editamos la descripción de los Shorts
# ya publicados (decisión de Nick, 2026-09-17). Incluye el permiso de subida.
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
TIMEOUT_SEGUNDOS = 30


def _post_por_defecto(url: str, **kwargs):
    return requests.post(url, timeout=TIMEOUT_SEGUNDOS, **kwargs)


def url_de_autorizacion(client_id: str, redirect_uri: str) -> str:
    """El enlace que se abre una sola vez para autorizar la aplicación.

    `access_type=offline` es lo que hace que Google devuelva refresh token, y
    `prompt=consent` lo fuerza incluso si el usuario ya autorizó antes: sin eso,
    una segunda autorización vuelve sin refresh token y el flujo queda a medias.
    """
    parametros = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{parametros}"


def _pedir_token(datos: dict, http_post: Callable[..., Any]) -> dict | None:
    try:
        respuesta = http_post(TOKEN_URL, data=datos)
    except Exception as exc:  # noqa: BLE001 - degradación segura
        logger.warning("No se pudo hablar con el endpoint de token: %s", exc)
        return None
    if getattr(respuesta, "status_code", None) != 200:
        logger.warning("Token rechazado: HTTP %s", getattr(respuesta, "status_code", "?"))
        return None
    try:
        cuerpo = respuesta.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Respuesta de token ilegible: %s", exc)
        return None
    if not isinstance(cuerpo, dict):
        logger.warning("Respuesta de token inválida: la respuesta no es un objeto")
        return None
    return cuerpo


def autorizar(
    codigo: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    *,
    http_post: Callable[..., Any] = _post_por_defecto,
) -> tuple[str, str] | None:
    """Canje único del código de autorización. Se hace una sola vez, a mano."""
    cuerpo = _pedir_token(
        {
            "grant_type": "authorization_code",
            "code": codigo,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        http_post,
    )
    if not cuerpo or "access_token" not in cuerpo or "refresh_token" not in cuerpo:
        return None
    return cuerpo["access_token"], cuerpo["refresh_token"]


def renovar_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    *,
    http_post: Callable[..., Any] = _post_por_defecto,
) -> str | None:
    cuerpo = _pedir_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        http_post,
    )
    return cuerpo.get("access_token") if cuerpo else None


SUBIDA_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CATEGORIA_TECNOLOGIA = "28"
# Casa, ropa y belleza: lo que sube el canal de Lanny.
CATEGORIA_ESTILO = "26"


def _put_por_defecto(url: str, **kwargs):
    return requests.put(url, timeout=TIMEOUT_SEGUNDOS, **kwargs)


def subir_short(
    ruta: str,
    titulo: str,
    descripcion: str,
    access_token: str,
    *,
    privado: bool = False,
    categoria: str = CATEGORIA_TECNOLOGIA,
    http_post: Callable[..., Any] = _post_por_defecto,
    http_put: Callable[..., Any] = _put_por_defecto,
) -> str | None:
    """Sube el video y devuelve su id. None ante cualquier fallo.

    Usa la subida reanudable en dos pasos: primero se abre la sesión con los
    metadatos y Google responde con una URL en la cabecera Location, después se
    manda el binario a esa URL. Es el modo recomendado para video y el único que
    tolera un corte sin empezar de cero.
    """
    metadatos = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion,
            "categoryId": categoria,
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "private" if privado else "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    try:
        inicio = http_post(
            f"{SUBIDA_URL}?uploadType=resumable&part=snippet,status",
            headers={"Authorization": f"Bearer {access_token}"},
            json=metadatos,
        )
    except Exception as exc:  # noqa: BLE001 - degradación segura
        logger.warning("No se pudo abrir la sesión de subida: %s", exc)
        return None
    if getattr(inicio, "status_code", None) != 200:
        # El motivo va en el log: "uploadLimitExceeded" es el tope diario del canal.
        logger.warning("Subida rechazada: HTTP %s %s", getattr(inicio, "status_code", "?"),
                       (getattr(inicio, "text", "") or "")[:300])
        return None
    destino = getattr(inicio, "headers", {}).get("Location")
    if not destino:
        logger.warning("Google no devolvió la URL de subida")
        return None

    try:
        with open(ruta, "rb") as archivo:
            respuesta = http_put(destino, data=archivo)
    except Exception as exc:  # noqa: BLE001 - degradación segura
        logger.warning("Falló la subida del archivo: %s", exc)
        return None
    if getattr(respuesta, "status_code", None) not in (200, 201):
        logger.warning("Subida incompleta: HTTP %s", getattr(respuesta, "status_code", "?"))
        return None
    try:
        cuerpo = respuesta.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Respuesta de subida ilegible: %s", exc)
        return None
    if not isinstance(cuerpo, dict):
        logger.warning("Respuesta de subida inválida: la respuesta no es un objeto")
        return None
    return cuerpo.get("id") or None



VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def hacer_publico(
    video_id: str,
    access_token: str,
    *,
    http_put: Callable[..., Any] = _put_por_defecto,
) -> bool:
    """Pasa a publico un video ya subido. False ante cualquier fallo.

    `videos.update` reemplaza el `status` entero: lo que no se manda vuelve al
    default, por eso va tambien `selfDeclaredMadeForKids`."""
    cuerpo = {"id": video_id,
              "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    try:
        r = http_put(f"{VIDEOS_URL}?part=status",
                     headers={"Authorization": f"Bearer {access_token}"}, json=cuerpo)
    except Exception as exc:  # noqa: BLE001 - degradación segura
        logger.warning("No se pudo cambiar la privacidad de %s: %s", video_id, exc)
        return False
    if getattr(r, "status_code", None) != 200:
        logger.warning("Cambio de privacidad rechazado en %s: HTTP %s", video_id,
                       getattr(r, "status_code", "?"))
        return False
    return True


COMENTARIOS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def comentar(
    video_id: str,
    texto: str,
    access_token: str,
    *,
    http_post: Callable[..., Any] = _post_por_defecto,
) -> bool:
    """Deja `texto` como comentario del canal en el video. False ante cualquier fallo.

    La API no permite fijar el comentario: eso se hace a mano en Studio."""
    cuerpo = {"snippet": {"videoId": video_id,
                          "topLevelComment": {"snippet": {"textOriginal": texto}}}}
    try:
        r = http_post(f"{COMENTARIOS_URL}?part=snippet",
                      headers={"Authorization": f"Bearer {access_token}"}, json=cuerpo)
    except Exception as exc:  # noqa: BLE001 - degradación segura
        logger.warning("No se pudo comentar el video %s: %s", video_id, exc)
        return False
    if getattr(r, "status_code", None) != 200:
        logger.warning("Comentario rechazado en %s: HTTP %s", video_id,
                       getattr(r, "status_code", "?"))
        return False
    return True
