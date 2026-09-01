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
# Caso DISTINTO al de arriba, y por eso mensaje distinto: el producto se lee
# perfecto, lo único que le falta es el descuento para armar el "De X por Y".
# Cuando los dos casos compartían mensaje, un producto sano con 0% de descuento
# parecía un link roto y se descartaba sin motivo (visto en vivo, 2026-09-01).
_ERROR_SIN_DESCUENTO = (
    "Ese producto lo leí bien, pero Shopee no le marca descuento ahora mismo, así que "
    "no puedo armar el post de oferta (el \"De R$ X por R$ Y\"). Si querés lo publico "
    "igual, con el precio a secas."
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
    # True solo cuando el error es "no tiene descuento": le dice al bot que puede
    # ofrecer publicarlo igual. Un link ilegible NO lo activa — ahí no hay nada
    # que publicar.
    sin_descuento: bool = False


def generate_post_reply(
    text: str,
    app_id: str,
    secret: str,
    hooks: HookBank,
    *,
    user_credentials: tuple[str, str] | None = None,
    permitir_sin_descuento: bool = False,
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

    `permitir_sin_descuento`: por defecto un producto sin descuento se rechaza (el
    canal es de ofertas). Con esto en True se arma igual, sin la línea de "% OFF" —
    es lo que pide el usuario cuando contesta "Publicar igual".
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
    if offer is None:
        return BotReply(error=_ERROR_NO_RESUELVE)
    if not offer.tiene_descuento and not permitir_sin_descuento:
        return BotReply(error=_ERROR_SIN_DESCUENTO, sin_descuento=True)

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

# Prompt para el generador de video. Se arma por bloques en vez de estar escrito
# entero, porque varia en DOS ejes independientes (formato x personas) y escribir
# las 6 combinaciones a mano garantiza que se desincronicen.
#
# Cosas que este prompt tiene que lograr, aprendidas probando, no razonando:
#
# 1. NO pelear por el formato 9:16. El generador lo ignora igual (el aspect ratio
#    es un parametro de generacion que la app de Gemini no expone), y la salida se
#    reencuadra despues con `video_vertical`. Pedirlo por texto solo confundia al
#    modelo, que llegaba a componer un mockup de celular para rellenar el alto.
#
# 2. SI exigir que el producto quede CENTRADO y quieto cuando la salida se va a
#    recortar: el reencuadre que quedo mejor se queda con la franja central del
#    video horizontal, asi que todo lo que se vaya a los costados se pierde.
#
# 3. DEJAR que aparezca lo que el producto necesita para funcionar. La version
#    anterior prohibia "objetos novos" y a la vez pedia "o produto em uso": para
#    una churrasqueira eso es contradictorio, porque la carne y el humo son
#    objetos nuevos. El modelo resolvia la contradiccion mostrando el producto
#    girando en el vacio, que es justo lo que no vende.

# Encuadre estricto: solo cuando la salida se va a recortar a la franja central.
_BLOQUE_ENCUADRE_RECORTE = """
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
"""

# Con salida 9:16 nativa (Google Flow) el video no se recorta, asi que exigir la
# franja central le limitaria la composicion al modelo por un motivo que no aplica.
_BLOQUE_ENCUADRE_LIBRE = """
ENQUADRAMENTO:
O produto deve ocupar boa parte do quadro e ficar sempre bem visível.
Movimentos suaves de câmera e zoom leve.
"""

_BLOQUE_PRODUCTO = """
PRODUTO:
Idêntico ao da imagem: mesmo formato, cores, materiais, proporções e detalhes.
REMOVA todo o texto, setas, selos e marcas d'água que apareçam na imagem de
referência. O produto deve aparecer limpo, sem nenhuma palavra sobre ele.

O produto deve aparecer FUNCIONANDO, fazendo aquilo para o que serve, junto com
o que for necessário para isso (por exemplo: carne grelhando e fumaça em uma
churrasqueira, roupas dobradas em um organizador, água em uma chaleira, sujeira
saindo em um produto de limpeza). Mostrar o resultado real do produto é o mais
importante do vídeo.
NÃO adicione objetos decorativos sem relação com o uso do produto.
"""

_BLOQUE_RITMO = """
RITMO:
0-3s: o produto em destaque.
3-7s: o produto em uso, mostrando o que ele faz.
7-10s: enquadramento final claro do produto.

Fotorrealista, iluminação profissional, movimento natural.
"""

_BLOQUE_NARRACION = """
NARRAÇÃO (incluir sempre):
Adicione narração em português do Brasil, voz natural e clara, tom comercial
amigável e convincente. Uma frase curta que caiba confortavelmente em 10 segundos.
Fale apenas de características reais e visíveis do produto.
NÃO invente informações, preços, promoções nem prazos de entrega.
"""

# Los tres modos de personas. El default es SIN: las manos son lo que peor generan
# los modelos de video, y una mano deformada arruina el video entero.
SIN_PERSONAS = "sin"
CON_MANOS = "manos"
CON_PERSONAS = "personas"

_BLOQUE_PERSONAS = {
    SIN_PERSONAS: """
PESSOAS:
NÃO mostre pessoas, mãos nem partes do corpo.
""",
    CON_MANOS: """
PESSOAS:
Podem aparecer MÃOS usando o produto de forma natural e realista, com anatomia
correta: cinco dedos, proporções normais, movimentos verossímeis.
NÃO mostre rostos, corpos nem outras partes do corpo além das mãos.
""",
    CON_PERSONAS: """
PESSOAS:
Pode aparecer UMA pessoa adulta usando o produto de forma natural, com anatomia
correta e movimentos verossímeis.
A pessoa NÃO deve falar para a câmera nem dar depoimento sobre o produto.
""",
}

# Regla dura: no depende del modo elegido y ningun modificador puede levantarla.
_BLOQUE_PROHIBICIONES = """
NÃO adicione texto novo, logotipos nem animais.
NÃO mostre telefone, moldura, tela ou interface de aplicativo.
NÃO mostre crianças ou bebês."""

_ENCABEZADO_RECORTE = "Anime esta imagem de referência em um vídeo publicitário de 10 segundos."
_ENCABEZADO_NATIVO = (
    "Anime esta imagem de referência em um vídeo publicitário vertical de 10 segundos."
)


# Palabras que Lanny puede agregar al final del comando. Se aceptan variantes con
# y sin acento porque el teclado del celular corrige solo y no vale perder un video
# por una tilde.
_MODIFICADORES_PERSONAS = {
    "manos": CON_MANOS,
    "maos": CON_MANOS,
    "mãos": CON_MANOS,
    "personas": CON_PERSONAS,
    "pessoas": CON_PERSONAS,
    "persona": CON_PERSONAS,
}


def leer_modificadores(texto: str) -> tuple[bool, str]:
    """Devuelve (nativo, personas) leyendo las palabras sueltas del comando.

    Se buscan las palabras en cualquier posicion y no solo al final: la version
    anterior usaba `endswith("nativo")`, que se rompe apenas hay dos modificadores
    porque "... nativo manos" ya no termina en "nativo".

    Una palabra desconocida no activa nada: el default es el modo mas seguro, y
    no queremos que un dedazo meta una persona en el video."""
    palabras = {_sin_tildes(p) for p in texto.lower().split()}
    nativo = "nativo" in palabras
    personas = SIN_PERSONAS
    for palabra, modo in _MODIFICADORES_PERSONAS.items():
        if _sin_tildes(palabra) in palabras:
            personas = modo
            break
    return nativo, personas


def _sin_tildes(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def construir_prompt_video(*, nativo: bool = False, personas: str | None = None) -> str:
    """Arma el prompt para los dos ejes: formato de salida y presencia de personas.

    `personas`: None o "sin" (default, nadie), "manos" (manos sin caras) o
    "personas" (una persona adulta). Un valor desconocido cae al default, que es
    el mas seguro: es preferible un video sin personas que uno con manos rotas."""
    bloque_personas = _BLOQUE_PERSONAS.get(personas or SIN_PERSONAS, _BLOQUE_PERSONAS[SIN_PERSONAS])
    partes = [
        _ENCABEZADO_NATIVO if nativo else _ENCABEZADO_RECORTE,
        _BLOQUE_ENCUADRE_LIBRE if nativo else _BLOQUE_ENCUADRE_RECORTE,
        _BLOQUE_PRODUCTO,
        _BLOQUE_RITMO,
        _BLOQUE_NARRACION,
        bloque_personas,
        _BLOQUE_PROHIBICIONES,
    ]
    return "\n\n".join(p.strip("\n") for p in partes)


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
    personas: str | None = None,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
    fetch_image: Callable[[str], bytes] | None = None,
) -> VideoReference:
    """Resuelve el link de Shopee, baja la foto del producto y devuelve el lienzo
    vertical 1080x1920 con el prompt de video.

    `nativo`: True si el generador produce 9:16 por si mismo (Flow), False si la
    salida se va a reencuadrar despues. Cambia el prompt, no la imagen.

    `personas`: quien puede aparecer en el video — None/"sin" (default), "manos" o
    "personas". Tambien cambia solo el prompt.

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
        prompt=construir_prompt_video(nativo=nativo, personas=personas),
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
