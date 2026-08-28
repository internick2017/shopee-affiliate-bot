"""Lógica pura del bot generador de posts: dado el texto que un usuario mandó por
Telegram, arma la respuesta (foto + caption) o el mensaje de error. No importa nada
de la librería de Telegram — eso vive en `bot_generador.py`, que es un wrapper fino
alrededor de `generate_post_reply`.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from .post_builder import HookBank
from .shopee_resolver import extract_shopee_shortlinks, resolve_shopee_offer
from .bot_mensajes import aviso_rango
from .shopee_review import _build_post_propio
from .vertical_canvas import build_vertical_canvas

_ERROR_SIN_LINK = "No encontré ningún link de Shopee en tu mensaje. Mandame el link del producto."
_ERROR_NO_RESUELVE = (
    "No pude leer ese producto en Shopee. Puede ser un link vencido, de cupón/campaña "
    "en vez de producto, o Shopee no lo tiene en su catálogo de afiliados ahora mismo."
)


@dataclass
class BotReply:
    """Lo que el bot le contesta al usuario. `error` presente = `caption`/`photo_url`
    ausentes, y viceversa — nunca los tres a la vez."""

    caption: str | None = None
    # Advertencia para Lanny, SEPARADA del caption a proposito: el post que se
    # publica queda intacto (el precio anunciado es el de partida, y esta bien),
    # esto es solo para que ella sepa que hay variaciones mas caras.
    aviso: str | None = None
    photo_url: str | None = None
    error: str | None = None


def generate_post_reply(
    text: str,
    app_id: str,
    secret: str,
    hooks: HookBank,
    *,
    user_credentials: tuple[str, str] | None = None,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
) -> BotReply:
    """Toma UN link de Shopee del texto (el primero, si hay varios) y arma el post.

    Solo usa el primer link: el bot está pensado para "un link, un post", a
    diferencia del pipeline automático que maneja mensajes de fuentes con varios
    links (producto + cupón) — acá el usuario manda un link a la vez.

    `user_credentials`: si el usuario registró su propia cuenta de Shopee Affiliate
    (`app_id`, `secret`), se usa para resolver, y el post lleva SU link propio. Sin
    registrar, `app_id`/`secret` (la cuenta por defecto) solo se usan para leer los
    datos del producto — el post lleva el link tal cual lo mandó el usuario, no el
    de la cuenta por defecto (retaguearlo sería monetizar para la cuenta equivocada).
    """
    links = extract_shopee_shortlinks(text)
    if not links:
        return BotReply(error=_ERROR_SIN_LINK)
    link_original = links[0]

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    resolve_app_id, resolve_secret = user_credentials or (app_id, secret)
    offer = resolve_shopee_offer(link_original, resolve_app_id, resolve_secret, **resolve_kwargs)
    if offer is None or not offer.tiene_descuento:
        return BotReply(error=_ERROR_NO_RESUELVE)

    if user_credentials is None:
        offer = replace(offer, link_propio=link_original)

    caption = _build_post_propio(offer, None, hooks.next())
    return BotReply(
        caption=caption,
        photo_url=offer.imagen_url,
        aviso=aviso_rango(offer.precio_min, offer.precio_max),
    )


_ERROR_SIN_FOTO = (
    "Pude leer el producto pero no conseguí bajar la foto de Shopee. Probá de nuevo en un rato."
)

# Prompt para el generador de video. Dos cosas que este prompt tiene que lograr y
# que se aprendieron probando, no razonando:
#
# 1. NO pelear por el formato 9:16. El generador lo ignora igual (el aspect ratio
#    es un parametro de generacion que la app de Gemini no expone), y la salida se
#    reencuadra despues con `video_vertical`. Pedirlo por texto solo confundia al
#    modelo, que llegaba a componer un mockup de celular para rellenar el alto.
#
# 2. SI exigir que el producto quede CENTRADO y quieto. Esto es nuevo: el modo de
#    reencuadre que quedo mejor es el recorte, que se queda solo con la franja
#    central del video horizontal. Todo lo que se vaya a los costados se pierde,
#    asi que el encuadre del video generado tiene que anticipar ese recorte.
# Variante para generadores que YA producen 9:16 nativo (Google Flow tiene el
# control de formato que la app de Gemini no expone). Ahi el video no se recorta
# despues, asi que la restriccion de "todo en la franja central" sobra: le estaria
# limitando la composicion al modelo por un motivo que no aplica. Lo que SI se
# mantiene es sacar el texto quemado en la foto del vendedor, que es independiente
# del formato.
_PROMPT_VIDEO_NATIVO = """Anime esta imagem de referência em um vídeo publicitário
vertical de 10 segundos.

PRODUTO:
Idêntico ao da imagem: mesmo formato, cores, materiais, proporções e detalhes.
REMOVA todo o texto, setas, selos e marcas d'água que apareçam na imagem de
referência. O produto deve aparecer limpo, sem nenhuma palavra sobre ele.
O produto deve ocupar boa parte do quadro e ficar sempre bem visível.

RITMO:
0-3s: o produto em destaque.
3-7s: detalhes do produto ou o produto em uso.
7-10s: enquadramento final claro do produto.

Movimentos suaves de câmera e zoom leve. Fotorrealista, iluminação profissional,
movimento natural.

NARRAÇÃO (incluir sempre):
Adicione narração em português do Brasil, voz natural e clara, tom comercial
amigável e convincente. Uma frase curta que caiba confortavelmente em 10 segundos.
Fale apenas de características reais e visíveis do produto.
NÃO invente informações, preços, promoções nem prazos de entrega.

NÃO adicione texto novo, logotipos, pessoas, animais nem objetos novos.
NÃO mostre telefone, moldura, tela ou interface de aplicativo.
NÃO mostre crianças ou bebês."""


_PROMPT_VIDEO = """Anime esta imagem de referência em um vídeo publicitário de 10 segundos.

ENQUADRAMENTO - O MAIS IMPORTANTE:
O produto deve ficar SEMPRE CENTRALIZADO, no meio exato do quadro, do primeiro ao
último segundo. O vídeo vai ser recortado depois na faixa central, então tudo que
ficar nas laterais será perdido.
- Mantenha o produto no centro em todos os momentos.
- NÃO mova o produto para a esquerda nem para a direita.
- NÃO use movimentos laterais de câmera, travelling nem panorâmica.
- Use apenas zoom suave para dentro ou para fora, sempre centrado no produto.
- NÃO coloque nada importante perto das bordas esquerda e direita.
- O produto deve ocupar boa parte da altura do quadro.

PRODUTO:
Idêntico ao da imagem: mesmo formato, cores, materiais, proporções e detalhes.
REMOVA todo o texto, setas, selos e marcas d'água que apareçam na imagem de
referência. O produto deve aparecer limpo, sem nenhuma palavra sobre ele.

RITMO:
0-3s: o produto em destaque, centralizado.
3-7s: detalhes do produto ou o produto em uso, sempre centralizado.
7-10s: enquadramento final claro do produto, centralizado.

Fotorrealista, iluminação profissional, movimento natural.

NARRAÇÃO (incluir sempre):
Adicione narração em português do Brasil, voz natural e clara, tom comercial
amigável e convincente. Uma frase curta que caiba confortavelmente em 10 segundos.
Fale apenas de características reais e visíveis do produto.
NÃO invente informações, preços, promoções nem prazos de entrega.

NÃO adicione texto novo, logotipos, pessoas, animais nem objetos novos.
NÃO mostre telefone, moldura, tela ou interface de aplicativo.
NÃO mostre crianças ou bebês."""


@dataclass
class VideoReference:
    """Imagen 9:16 lista para un generador de video, más el prompt sugerido.
    `error` presente = el resto ausente, igual que `BotReply`.

    `caption` y `prompt` van separados porque el caption de Telegram corta en 1024
    caracteres y el prompt solo pasa de eso: mandarlos juntos truncaba justo las
    instrucciones del final, que son las restricciones."""

    image_bytes: bytes | None = None
    caption: str | None = None
    prompt: str | None = None
    link: str | None = None
    # Identidad del producto, para anotarlo como grabado y no volver a ofrecerlo.
    item_id: int | None = None
    aviso: str | None = None
    filename: str | None = None
    error: str | None = None


def generate_video_reference(
    text: str,
    app_id: str,
    secret: str,
    *,
    user_credentials: tuple[str, str] | None = None,
    nativo: bool = False,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
    fetch_image: Callable[[str], bytes] | None = None,
) -> VideoReference:
    """Resuelve el link de Shopee, baja la foto del producto y devuelve el lienzo
    vertical 1080x1920 con el prompt de video.

    `nativo`: True si el generador produce 9:16 por si mismo (Flow), False si la
    salida se va a reencuadrar despues. Cambia el prompt, no la imagen.

    `fetch_image` se inyecta para los tests; por defecto baja con `requests`."""
    links = extract_shopee_shortlinks(text)
    if not links:
        return VideoReference(error=_ERROR_SIN_LINK)

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    resolve_app_id, resolve_secret = user_credentials or (app_id, secret)
    offer = resolve_shopee_offer(links[0], resolve_app_id, resolve_secret, **resolve_kwargs)
    if offer is None:
        return VideoReference(error=_ERROR_NO_RESUELVE)
    if not offer.imagen_url:
        return VideoReference(error=_ERROR_SIN_FOTO)

    try:
        raw = (fetch_image or _bajar_imagen)(offer.imagen_url)
    except Exception:
        return VideoReference(error=_ERROR_SIN_FOTO)
    if not raw:
        return VideoReference(error=_ERROR_SIN_FOTO)

    return VideoReference(
        image_bytes=build_vertical_canvas(raw),
        caption=offer.titulo,
        prompt=_PROMPT_VIDEO_NATIVO if nativo else _PROMPT_VIDEO,
        link=offer.link_propio,
        item_id=offer.item_id,
        aviso=aviso_rango(offer.precio_min, offer.precio_max),
        filename="referencia-9x16.jpg",
    )


def _bajar_imagen(url: str) -> bytes:
    import requests

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content
