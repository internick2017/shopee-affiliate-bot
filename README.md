# Bot de ofertas (Amazon · Shopee · Mercado Livre)

Escucha canales de ofertas en Telegram y publica cada oferta en un canal privado tuyo,
listo para pasar a WhatsApp.

Las ofertas de **Amazon** se monetizan solas: el bot cambia el tag de afiliado por el
tuyo y arma el post con el estilo de Lanny. Las de **Mercado Livre** también se intentan
monetizar solas, pero con un paso más: si el shortlink `meli.la` resuelve a un producto
puntual y tiene descuento comprobable, el bot arma un post propio con el template de
Lanny y los datos reales de Mercado Livre (título, precio, descuento) consultados al
momento de publicar, no el texto de la fuente; si no resuelve (por ejemplo, un link de
lista/colección en vez de un producto) o no hay descuento comprobable, cae a reenviar la
oferta marcada a su canal para que generes el link a mano. Las de **Shopee** funcionan
igual mediante la Affiliate Open API de Shopee: si el link resuelve a un producto puntual
con descuento comprobable, el bot arma un post propio con el template de Lanny y los
datos reales de Shopee (título, precio, descuento), más el link de cupón/campaña
retagueado si el mensaje trae uno; si no, cae al mismo reenvío marcado de siempre.

## Cómo funciona

Cada mensaje se le ofrece a **todos** los handlers, no al primero que lo reclama
(`src/offer_pipeline.py`): un mensaje de Crowman trae un bloque de Amazon y otro de
Mercado Livre, y si el primer handler se lo quedara entero se perderían los demás
productos. Cada handler reclama por su propio dominio de links, así que no se pisan.
El mensaje que no reclama nadie se descarta.

| Handler | Detecta | Qué hace | Canal |
|---|---|---|---|
| `AmazonPipeline` | `amazon.com.br/dp/...`, `link.amazon/...`, `amzn.to/...` | re-taguea y arma el post | `TARGET_CHANNEL_ID` |
| `ShopeeReviewPipeline` | `shopee.com.br`, `shp.ee` | arma post propio (template Lanny + datos reales vía Affiliate Open API) si el link resuelve con descuento; si no, reenvía marcado | `SHOPEE_CHANNEL_ID` |
| `MercadoLivreReviewPipeline` | `meli.la`, `mercadolivre.com` | arma post propio (template Lanny + datos reales) si el link resuelve con descuento; si no, reenvía marcado | `ML_CHANNEL_ID` |

Detalles que no se ven en la tabla:

- **Fotos.** El post lleva la imagen del mensaje original, reenviada por referencia.
- **Un canal, sus productos.** En un mensaje mixto, el reenvío a Shopee/ML descarta los
  bloques de las otras plataformas: si no, el canal de ML recibiría los productos de
  Amazon —ya monetizados en su canal— con el tag de afiliado del competidor intacto.
- **Sin repetidos.** Los canales fuente se copian ofertas entre sí. `DedupStore` recuerda
  cada producto 7 días (Amazon por ASIN, el resto por link) y no lo vuelve a publicar.
  La clave se reserva con `claim()` antes de postear, de forma atómica, así que dos
  mensajes concurrentes con la misma oferta no la publican los dos. Si el post falla, se
  libera y se reintenta.
- **Shortlinks de Amazon.** `link.amazon/XXXX` no lleva el ASIN en la URL: el bot sigue el
  redirect y canonicaliza a `dp/{ASIN}`, descartando la atribución del afiliado de origen.
- **Precios.** Todo el parsing vive en `src/prices.py`. Entiende `De R$ 408 por R$ 167`,
  `DE 13,59 | POR 9,16`, `Por: R$ 6,66 (44% off)` y `28,99 à vista`.
- **Links.** Todas las regexes de URL viven en `src/links.py`, igual que los precios en
  `prices.py`. Es lo que le permite a un handler saber qué links son de otra plataforma.
- **Rate limit.** Ante un `FloodWait` de Telegram, `ChannelPoster` espera y reintenta, en
  vez de perder la oferta. Si Telegram pide más de 5 minutos, no bloquea el bot.

## Setup

1. `pip install -r requirements.txt`
2. Copiar `.env.example` a `.env` y completar:
   - `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`: gratis en https://my.telegram.org
   - `AMAZON_TAG`: tu tag de afiliado de Amazon (sin esto el bot no arranca)
   - `TARGET_CHANNEL_ID`: canal de los posts de Amazon
   - `SHOPEE_CHANNEL_ID` / `ML_CHANNEL_ID`: canal de Shopee y de Mercado Livre (en ambos:
     post propio o reenvío manual, según si el link resuelve con descuento). Los canales
     se buscan **por nombre** entre tus chats. Si dejas uno vacío, esas ofertas van al
     canal principal con un warning; si lo pones y el canal no existe, el bot **no
     arranca** (mejor fallar que publicar en el canal equivocado).
   - `SHOPEE_APP_ID` / `SHOPEE_SECRET`: credenciales de la Affiliate Open API de Shopee
     (Portal de Afiliados > API). Vacíos = el bot nunca intenta el post automático y
     todas las ofertas de Shopee van marcadas a `SHOPEE_CHANNEL_ID` (el apagador de esta
     feature).
   - `ML_MATT_WORD` / `ML_MATT_TOOL`: tag de campaña y cuenta de afiliado de Mercado
     Livre, de la Central de Afiliados de Mercado Livre (perfil > tus datos). Vacíos =
     el bot nunca intenta el post automático y todas las ofertas de ML van marcadas a
     `ML_CHANNEL_ID` (el apagador de esta feature).
   - `SOURCE_CHATS`: canales a escuchar, separados por coma (vacío = todos)
3. Editar `hooks.txt` para ajustar los ganchos.

La primera corrida pide tu teléfono y el código de Telegram; después reusa
`shopee_user_session.string`.

## Correr

```bash
python run_ofertas.py            # el bot
python run_ofertas.py --observe  # diagnóstico: loguea cada mensaje y su chat_id, sin postear
```

### Bot generador de posts

En chat privado, un usuario de `BOT_ALLOWED_USERS` puede:

| Manda | Recibe |
|---|---|
| un link de Shopee | el post armado (foto + caption con su link de afiliado) |
| `/ideas <categoria o palabra>` | top 5 productos VARIADOS para grabar, ranqueados por retorno por venta, ventas, rating y precio |
| `/ventas [dias]` | que se vendio de verdad: comision, banda de precio y los que mas dejaron (default 30 dias) |
| `/tendencia [dias]` | que esta despegando AHORA (necesita 2+ dias de muestreo, ver abajo) |
| `/video <link>` | la imagen 9:16 de referencia + el prompt + el link del producto |
| `/video <link> nativo` | igual, pero con el prompt para generadores que ya producen 9:16 (Google Flow) |
| un archivo de video | el mismo video en 1080x1920, en sus dos versiones: RECORTE (pantalla completa, corta los costados) y MARCO (video entero con fondo difuminado) |
| `/registrar_shopee <app_id> <secret>` | guarda sus credenciales propias |
| `/olvidar_shopee` | las borra |

El formato de salida de Veo es un parametro de generacion (`aspect_ratio`, default
16:9) que la app de Gemini no expone, por eso el video se reencuadra despues en vez
de pedirlo por prompt.

En Windows, sin ventana visible: `iniciar-bot-ofertas-oculto.vbs` (o
`iniciar-todo-oculto.vbs` para arrancar tambien el bot generador de posts).
Para pararlos: `detener-bots-ocultos.vbs`.

## Antes de agregar un canal fuente

Cada canal postea con un formato distinto, y el que no encaja se descarta en silencio.
Baja sus mensajes con `python fetch_mensajes.py "<nombre>" 40` y pásalos por el
`OfferPipeline` con un poster falso: el conteo de posts contra descartes te dice qué
formato de precio o de link falta cubrir.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q       # los tests
ruff check .    # estilo
mypy src        # tipos
```

Las tres cosas corren en CI (`.github/workflows/ci.yml`) en cada push y PR.
`ruff format` está configurado pero todavía no aplicado: reformatearía casi todo el
repo, así que conviene hacerlo en un commit propio antes de sumarlo al CI.

## Muestreo diario (detector de tendencia)

`productOfferV2` devuelve `sales` como un acumulado historico: dice que vendio
mucho SIEMPRE, que suele ser lo mas saturado. Para saber que esta despegando AHORA
hay que guardar ese numero cada dia y mirar la diferencia.

```bash
python run_snapshot.py            # todas las categorias (~30s)
python run_snapshot.py beleza     # solo una
```

En Windows, sin ventana: `muestreo-diario.vbs`. Conviene agendarlo una vez por dia
en el Programador de tareas. Correrlo dos veces el mismo dia no duplica datos.

`/tendencia` necesita al menos 2 dias de muestreo para tener una derivada que
calcular; con menos avisa cuantos dias lleva.
