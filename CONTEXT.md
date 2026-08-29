# Glosario del dominio — shopee-affiliate-bot

## Bot generador de posts

Bot de Telegram (`python-telegram-bot`, proceso separado de `run_ofertas.py`/Telethon)
que un usuario whitelisted usa en chat privado: pega un link de Shopee (afiliado o
crudo) y el bot le devuelve un **post propio** listo (foto + caption) para publicar
a mano. No publica solo — distinto del pipeline de auto-post/revisión existente
(`ReviewPipeline`, `ChannelPoster`), que corre sobre las fuentes reenviadas al canal.

## Whitelist de acceso

Lista de `user_id` de Telegram permitidos para usar el bot generador, en
`BOT_ALLOWED_USERS` (`.env`). Existe desde el MVP para que la decisión de a quién
se le abre el bot (y si se cobra) quede en manos del operador más adelante, sin
tener que rearquitecturar el control de acceso después.

## Modos de personas en el prompt de video

Los tres valores que acepta `/video` para decidir quién puede aparecer:
`sin` (default, solo el producto), `manos` (manos sin caras) y `personas` (una
persona adulta). El default es `sin` porque las manos son lo que peor generan los
modelos de video. Es independiente del eje `nativo`, que decide el formato de
salida. La prohibición de niños y bebés no es un modo: va en las tres variantes y
ningún modificador la levanta.
