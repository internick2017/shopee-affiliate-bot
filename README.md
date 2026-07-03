# Shopee Affiliate Bot

Escucha ofertas de Shopee en Telegram, arma un post con el estilo de Lanny y lo
entrega a un canal privado de Telegram para publicar a mano en WhatsApp.

## Setup

1. `pip install -r requirements.txt`
2. Copiar `.env.example` a `.env` y completar:
   - `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`: gratis en https://my.telegram.org
   - `TARGET_CHANNEL_ID`: el canal privado donde se publican los posts
   - `SOURCE_CHATS`: IDs o nombres de los grupos a escuchar (coma-separados; vacío = todos)
   - `SHOPEE_APP_ID` / `SHOPEE_SECRET`: del panel de afiliado (opcional hasta Fase 3)
3. Editar `hooks.txt` para ajustar los ganchos.

## Correr

- Descubrir grupos y confirmar que pesca links: `python run.py --observe`
- Correr el pipeline: `python run.py`

Sin credenciales de Shopee usa datos de prueba (MockShopeeClient).

## Tests

`python -m pytest`
