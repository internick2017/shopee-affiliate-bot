# Bot de ofertas (Amazon · Shopee · Mercado Livre)

Escucha canales de ofertas en Telegram y publica cada oferta en un canal privado tuyo,
listo para pasar a WhatsApp.

Las ofertas de **Amazon** se monetizan solas: el bot cambia el tag de afiliado por el
tuyo y arma el post con el estilo de Lanny. Las de **Shopee** y **Mercado Livre** no se
pueden re-taguear por URL, así que llegan marcadas a su propio canal para que generes el
link a mano.

## Cómo funciona

Cada mensaje recorre una lista ordenada de handlers y lo atiende el primero que lo
reclama (`src/offer_pipeline.py`). El que no reclama nadie se descarta.

| Handler | Detecta | Qué hace | Canal |
|---|---|---|---|
| `AmazonPipeline` | `amazon.com.br/dp/...`, `link.amazon/...`, `amzn.to/...` | re-taguea y arma el post | `TARGET_CHANNEL_ID` |
| `ShopeeReviewPipeline` | `shopee.com.br`, `shp.ee` | reenvía marcado | `SHOPEE_CHANNEL_ID` |
| `MercadoLivreReviewPipeline` | `meli.la`, `mercadolivre.com` | reenvía marcado | `ML_CHANNEL_ID` |

Detalles que no se ven en la tabla:

- **Fotos.** El post lleva la imagen del mensaje original, reenviada por referencia.
- **Sin repetidos.** Los canales fuente se copian ofertas entre sí. `DedupStore` recuerda
  cada producto 7 días (Amazon por ASIN, el resto por link) y no lo vuelve a publicar.
- **Shortlinks de Amazon.** `link.amazon/XXXX` no lleva el ASIN en la URL: el bot sigue el
  redirect y canonicaliza a `dp/{ASIN}`, descartando la atribución del afiliado de origen.
- **Precios.** Todo el parsing vive en `src/prices.py`. Entiende `De R$ 408 por R$ 167`,
  `DE 13,59 | POR 9,16`, `Por: R$ 6,66 (44% off)` y `28,99 à vista`.

## Setup

1. `pip install -r requirements.txt`
2. Copiar `.env.example` a `.env` y completar:
   - `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`: gratis en https://my.telegram.org
   - `AMAZON_TAG`: tu tag de afiliado de Amazon (sin esto el bot no arranca)
   - `TARGET_CHANNEL_ID`: canal de los posts de Amazon
   - `SHOPEE_CHANNEL_ID` / `ML_CHANNEL_ID`: canales de reenvío manual. Los canales se
     buscan **por nombre** entre tus chats. Si dejas uno vacío, esas ofertas van al canal
     principal con un warning; si lo pones y el canal no existe, el bot **no arranca**
     (mejor fallar que publicar en el canal equivocado).
   - `SOURCE_CHATS`: canales a escuchar, separados por coma (vacío = todos)
3. Editar `hooks.txt` para ajustar los ganchos.

La primera corrida pide tu teléfono y el código de Telegram; después reusa
`shopee_user_session.string`.

## Correr

```bash
python run_ofertas.py            # el bot
python run_ofertas.py --observe  # diagnóstico: loguea cada mensaje y su chat_id, sin postear
```

En Windows: `iniciar-bot-ofertas.bat`.

## Antes de agregar un canal fuente

Cada canal postea con un formato distinto, y el que no encaja se descarta en silencio.
Baja sus mensajes con `python fetch_mensajes.py "<nombre>" 40` y pásalos por el
`OfferPipeline` con un poster falso: el conteo de posts contra descartes te dice qué
formato de precio o de link falta cubrir.

## Tests

`python -m pytest`

## `run.py` (obsoleto)

Es el pipeline original, que consultaba la API de afiliado de Shopee para armar el post.
Quedó sin terminar (`RealShopeeClient.fetch` es un `NotImplementedError`) y **no es el
bot que corre hoy**. Se conserva por la integración con la API, que se retomará cuando
haya credenciales de Shopee.
