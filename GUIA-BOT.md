# Guía del bot de Telegram

Todo se hace hablándole al bot por chat privado. No hace falta instalar nada ni
usar la computadora: funciona desde el celular.

---

## El flujo de todos los días

**1. Pedile ideas de qué grabar**

```
/ideas casa
```

Te devuelve 5 productos distintos, elegidos por cuánta plata te dejan por venta,
cuánto se venden, la calificación y el precio. Cada uno viene con su link ya
listo para ganar comisión.

**2. Elegí uno y pedí la referencia para el video**

```
/video https://s.shopee.com.br/7fZMtuvwYO nativo
```

Copiá el link del producto que elegiste en el paso 1. El bot te manda tres cosas:

- una imagen vertical del producto, lista para el generador de video
- el texto (prompt) para pegarle al generador
- el link del producto, para tenerlo a mano cuando publiques

**3. Generá el video en Google Flow**

Subí la imagen, pegá el prompt, y elegí formato vertical 9:16.

**4. Publicá**

El link del producto te lo dio el bot en el paso 2.

---

## Los comandos

### `/ideas`

Qué productos conviene grabar.

| Cómo lo escribís | Qué hace |
|---|---|
| `/ideas` | Te lista todas las categorías disponibles |
| `/ideas beleza` | Los 5 mejores de esa categoría |
| `/ideas porta frios` | Busca esas palabras exactas |

**Categorías:** casa, cozinha, limpeza, beleza, bebe, brinquedos, pet, saude,
suplementos, alimentos, eletrodomesticos, moda, calcados, acessorios, celular,
informatica, audio, esportes, automotivo, papelaria.

Si lo que buscás no está en la lista, escribilo igual y lo busca por palabra.

### `/video`

La imagen y el texto para generar el video.

| Cómo lo escribís | Cuándo usarlo |
|---|---|
| `/video <link> nativo` | Si generás en **Google Flow** (recomendado) |
| `/video <link>` | Si generás en un lugar que solo hace video horizontal |

La diferencia está en el texto que te da. La versión `nativo` es para cuando el
generador ya hace el video vertical. La otra le pide al generador que mantenga el
producto bien al centro, porque después hay que recortar el video.

### `/tendencia`

Qué productos están **subiendo ahora**. Es distinto de `/ideas`: ahí ves lo que
más vendió siempre, que suele ser lo que ya publicó todo el mundo. Acá ves lo que
está despegando esta semana, que es el mejor momento para grabarlo.

```
/tendencia
/tendencia 14
```

El número son los días que mira para atrás. Sin número, mira 7.

### `/ventas`

Cuánto se ganó de verdad.

```
/ventas
/ventas 90
```

Te muestra la comisión total, cuántas ventas hubo, el promedio por venta, y
cuáles productos dejaron más. También agrupa por rango de precio, que sirve para
ver qué tipo de producto conviene.

Sin número mira los últimos 30 días.

---

## Cosas que se mandan sin comando

### Un link de Shopee

Mandá el link solo, sin escribir nada más, y te devuelve el post armado: la foto
del producto y el texto listo para copiar y pegar en el canal.

### Un archivo de video

Mandá el video y te lo devuelve en formato vertical, listo para Shopee Video.
Te llegan **dos versiones** para que elijas:

- **RECORTE**: pantalla completa, sin bordes. Se ve mejor, pero corta los
  costados. Ideal si el producto está en el centro.
- **MARCO**: el video entero, con fondo difuminado arriba y abajo. No corta nada,
  pero se nota que el video no era vertical.

Probá las dos y quedate con la que mejor se vea.

---

## Tu cuenta de afiliada

Si querés que los links que te da el bot sean **tuyos** y no de la cuenta
compartida:

```
/registrar_shopee TU_APP_ID TU_SECRET
```

Para borrarlas: `/olvidar_shopee`

---

## Si algo no funciona

**El bot no responde.** Puede estar apagado. Avisale a Nick.

**"Ese video pesa más de 20 MB."** Telegram no deja mandarle archivos más grandes
al bot. Generá el video más corto o con menor calidad.

**"No pude leer ese producto en Shopee."** Suele pasar con links de cupón o de
campaña en vez de producto, o con links vencidos. Probá con otro.

**`/tendencia` dice que faltan días de datos.** Es normal al principio: necesita
al menos dos días midiendo para poder comparar. Al día siguiente ya anda.

---

## Consejos

**Grabá seguido, poco a poco.** Es mejor un par de videos por día que veinte de
golpe una vez por semana.

**Mirá `/ventas` cada tanto.** Es la única forma de saber si los videos están
sirviendo. Compará mes contra mes.

**Los productos más vendidos no siempre son los mejores.** Suelen pagar menos
comisión y ya los publicó mucha gente. Por eso `/ideas` no te los pone siempre
primero, y por eso existe `/tendencia`.

**Fijate en la comisión, no solo en el precio.** Un producto de R$ 100 al 12%
deja más que uno de R$ 10 al 30%.
