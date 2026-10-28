# Análisis del grupo de WhatsApp de ofertas de Lanny (2026-10-28)

Solo lectura: logs del bot (`logs/ofertas.log*`, 2026-09-17 a 2026-10-28), `dedup.db` y el
`conversionReport` de la Affiliate API de Shopee con las credenciales del `.env` (cuenta de
Lanny). No se mandó ningún mensaje ni se tocó código.

## Resumen en cinco líneas

1. El bot publica mucho más de lo que un grupo puede absorber: unas **85 ofertas de Shopee y
   358 de Mercado Livre por día** en los canales de Telegram. Lanny elige a mano qué pasa a
   WhatsApp, así que lo que llega al grupo no está medido en ningún lado.
2. Las ventas con origen WhatsApp son pocas pero pagan mejor que el video: **6 a 10 % sobre lo
   vendido** contra **4 a 5 %** de Shopee Video.
3. Hubo un **hueco total de ventas por WhatsApp del 3 al 21 de octubre** (cero items en 19
   días). Antes la semana buena dejaba R$ 42; desde el 22/10 volvió a vender, en poca cantidad.
4. Lo que se vende por WhatsApp es **variado y barato** (mediana R$ 29,90): moda infantil,
   belleza, ropa femenina, papelería, electrodomésticos chicos. Casa y Decoración es solo 7 de
   38 items.
5. La compra por WhatsApp es **impulsiva**: el 80 % compra dentro de los 25 minutos del clic, y
   los clics se concentran a las **16 h y a las 19 h**.

## 1. Qué se manda

El bot no publica en un solo canal: el `.env` tiene tres.

| canal de Telegram | qué recibe |
|---|---|
| Ofertas Lanny | Amazon (apagado desde 2026-09-15) |
| Ofertas Shopee | Shopee auto-monetizado con link de Lanny, o reenviado "a revisar" |
| Ofertas ML | Mercado Livre auto-monetizado, o reenviado "a revisar" |

De ahí Lanny copia y pega al grupo de WhatsApp. **No hay registro de qué copia**, así que todo
lo que sigue mide la oferta disponible, no lo que realmente llegó al grupo.

### Cantidad por día (41 días medidos)

| tienda | publicada auto | reenviada a revisar | total/día | descartada por comisión < 6 % |
|---|---|---|---|---|
| Shopee | 42,5 | 42,8 | **85** | 8,8 |
| Mercado Livre | 181,0 | 176,9 | **358** | (no aplica) |

Es muy irregular. Shopee va de 2 a 561 por día; los picos coinciden con fechas de campaña
(23/09: 338, **10/10: 561**, 14/10: 272, 21/10: 223). Los domingos baja (25/10: 6 de Shopee).
Además la mitad de lo que llega es "a revisar": sin link de Lanny hasta que alguien lo arme
a mano, o sea inutilizable para un envío automático.

### Horario de publicación (promedio por día)

- **Shopee:** un pico raro a las **00 h (26,5 por día)**, las ofertas relámpago de medianoche,
  y después solo 3 a 8 por hora durante el día (máximo 7,7 a las 9 h).
- **Mercado Livre:** pico a las **9 h (51) y 10 h (39)**, luego 20 a 30 por hora hasta las
  16 h, y baja a la noche.
- De 3 h a 6 h no sale nada.

### Rubros

El log no guarda el nombre del producto y `dedup.db` solo guarda los links cortos de las
fuentes (750 de Shopee y 2.601 de ML en los últimos 7 días), así que **el rubro de lo
publicado no se pudo medir** sin leer el canal de Telegram. No lo leí a propósito: la sesión
de Telethon la está usando el bot en vivo y abrirla dos veces puede invalidarla. Lo que sí se
sabe es el filtro: Shopee descarta lo que paga menos de 6 %, que en la práctica saca muchos
electrodomésticos.

## 2. Cómo rinde (Affiliate API, cuenta de Lanny)

171 items en los últimos 89 días (la API no deja ir más atrás de 3 meses). Cuento COMPLETED y
PENDING; los CANCELLED quedan afuera.

| período | origen | items | vendido | comisión | tasa |
|---|---|---|---|---|---|
| 0 a 30 días | Shopee Video | 79 | R$ 2.364,86 | R$ 97,32 | 4,1 % |
| 0 a 30 días | **WhatsApp** | **12** | R$ 367,38 | **R$ 22,65** | 6,2 % |
| 0 a 30 días | Others | 6 | R$ 215,22 | R$ 21,00 | 9,8 % |
| 30 a 60 días | Shopee Video | 30 | R$ 1.036,42 | R$ 49,35 | 4,8 % |
| 30 a 60 días | **WhatsApp** | **18** | R$ 726,49 | **R$ 72,13** | 9,9 % |
| 30 a 60 días | Others | 7 | R$ 235,87 | R$ 20,06 | 8,5 % |
| 60 a 89 días | Shopee Video | 2 | R$ 27,87 | R$ 3,82 | 13,7 % |
| 60 a 89 días | **WhatsApp** | **10** | R$ 238,38 | **R$ 23,72** | 10,0 % |
| 60 a 89 días | Others | 8 | R$ 221,08 | R$ 21,01 | 9,5 % |

De los 12 items de WhatsApp de los últimos 30 días, **7 siguen PENDING** (R$ 8,13); por eso la
medición de ayer, que contaba solo completados, daba 5 items y R$ 14,52. Coinciden.

### Comisión por semana, solo WhatsApp

| semana | comisión |
|---|---|
| W32 a W37 (ago a mediados de sep) | R$ 0,79 / 5,94 / 13,96 / 3,03 / 2,68 / 13,69 |
| **W38 (15 a 21/09)** | **R$ 42,82** (la mejor) |
| W39 / W40 | R$ 12,94 / R$ 14,52 |
| **W41 y W42 (3 al 21/10)** | **R$ 0** |
| W43 / W44 (hasta hoy) | R$ 5,69 / R$ 2,44 |

### Lo que se vendió por WhatsApp

Últimos 30 días (todos PENDING):

| fecha | producto | precio | comisión |
|---|---|---|---|
| 27/10 | Bolsa feminina baguete | R$ 20,90 | R$ 0,63 |
| 27/10 | Sandália infantil jelly corações | R$ 27,47 | R$ 0,82 |
| 26/10 | Lixadeira de unhas elétrica | R$ 32,98 | R$ 0,99 |
| 23/10 | Porta tempero giratório com potes de vidro | R$ 48,90 | R$ 2,05 |
| 22/10 | Macacão pantacurt listrado | R$ 27,99 | R$ 0,84 |
| 22/10 | Saída de praia plus size tricô | R$ 25,00 | R$ 1,65 |
| 22/10 | Casaquinho bebê inverno peluciado | R$ 38,27 | R$ 1,15 |

Completados en el período anterior (los que más dejaron): kit 25 caixas arquivo morto
(2 u., R$ 17,29), liquidificador Mondial L-99 (R$ 11,00), kit 3 calças infantis (R$ 9,00),
kit alecrim antiqueda (R$ 7,45), hidratante Kokeshi (R$ 6,52), pendrive (R$ 5,57), lençol
solteiro microfibra (R$ 4,48), balança digital (R$ 4,02), escova OralGos (R$ 4,19).

**Por categoría (38 items de WhatsApp en 89 días):** Moda Infantil 5, Casa e Decoração 7,
Beleza 5, Papelaria 5, Eletrodomésticos 4, Roupas Femininas 4, Saúde 2, Hobbies 2, el resto
uno cada uno. Lo que más comisión dejó fue papelería (R$ 18,09 en 30 a 60 días) y
electrodomésticos chicos (R$ 16,19).

**Precio:** mediana R$ 29,90, entre R$ 9,90 y R$ 109,99. **Tasa por item:** de 3 a 26 %; la
mitad de los items pagó 6 % o menos.

**Hora del clic** (cuando la gente toca el link): 16 h es la más fuerte (10 clics), después
19 h (5), y 9 h, 11 h y 15 h (4 cada una). **Del clic a la compra:** 31 de 38 compraron en
menos de 25 minutos.

## 3. Comparación con lo medido antes

- Lo dicho antes (WhatsApp cae de R$ 109 a R$ 20; últimos 30 días 5 items y R$ 14,52) se
  confirma, y ahora se ve **dónde** cayó: no fue una baja gradual, fue un corte. Del 3 al
  21 de octubre no hubo **ninguna** venta por WhatsApp. Eso apunta a que en esas semanas no
  se mandaron ofertas al grupo (o casi), más que a que el grupo dejó de comprar. Vale la
  pena preguntarle a Lanny qué pasó esas semanas.
- Desde el 22/10 volvió: 7 ventas en 6 días, pero todas baratas (comisión media R$ 1,16
  contra R$ 4 en septiembre). Se están vendiendo productos de 3 a 4 % de comisión.
- Shopee Video creció mucho (de 2 a 79 items por mes) y hoy trae 4 veces más comisión que
  WhatsApp, pero paga la mitad por real vendido. **WhatsApp sigue siendo el canal de mejor
  tasa**; el problema es volumen y constancia, no el canal.
- Mercado Livre no está en esta medición: sus ventas no salen por la API de Shopee. Si Lanny
  manda ofertas de ML al grupo, habría que mirarlas en el panel de afiliados de ML.

## 4. El plan decidido, contrastado con los datos

Plan original de Nick: 3 productos por hora de 8 h a 21 h, lunes a sábado, 80 % hogar y 20 %
de un rubro del día (lun masculino, mar belleza, mié electrónicos, jue niños, vie moda
femenina, sáb mezcla).

**Decidido el 2026-10-28, después de este análisis:**
- **2 productos por hora, fijo**, de 8 h a 21 h (26 a 28 por día), en vez de 3. Menos
  notificaciones por hora baja el riesgo de que la gente silencie el grupo.
- **80 % hogar se mantiene.** Lanny promociona el grupo como un grupo de hogar: lo que la
  gente espera al entrar manda sobre la mezcla de ventas pasadas.

**Lo que los datos apoyan:**
- **Lunes a sábado, sin domingo:** el domingo ya es el día más flojo en las fuentes, y
  descansar un día baja el riesgo de que la gente silencie el grupo.
- **Constancia todos los días:** el hueco de octubre muestra que, sin envíos, la venta
  cae a cero. Un horario fijo arregla exactamente eso.
- **Rubros rotativos:** los 5 rubros elegidos son justamente los que ya venden por WhatsApp
  (infantil, belleza, moda femenina, electrónicos, masculino).
- **Ventana 8 h a 21 h:** cubre casi todos los clics medidos (de 7 h a 22 h).

**Para tener en cuenta al medir:**
- **Las ventas pasadas fueron más variadas que 80 % hogar.** Casa e Decoração fue 7 de 38;
  contando "hogar" amplio (casa, electrodomésticos chicos, papelería, lençol) unas 17 de 38.
  Pero esas ventas vinieron de un grupo que recibía de todo, así que no contradicen el
  enfoque de hogar: solo dicen que el 20 % del rubro del día también vende. A los 30 días
  conviene mirar qué parte de la comisión vino de hogar y qué parte del rubro del día.
- **Los clics se concentran a la tarde** (casi la mitad entre 15 h y 19 h). Con 2 por hora
  fijos, conviene que los productos más fuertes del día caigan en ese tramo.
- **No hay oferta suficiente de hogar con link de Lanny para llenar el plan desde las
  fuentes.** Shopee da 3 a 8 ofertas por hora de día, la mitad sin link armado, y de esas
  solo una parte es hogar. Para cumplir el plan la lista del día tiene que salir de otro
  lado: el panel de ideas (`/ideas` y `/tendencia` con la API, por categoría) o una cola que
  se arme a la mañana con el día completo.

## 5. Automatizar el envío con el celular conectado

Hoy el paso a WhatsApp es manual. Ya existe la base para hacerlo por el celular:
`src/publicador_celular.py` maneja el Galaxy A07 por ADB (scrcpy + uiautomator2) para Shopee
Video. Un envío a un grupo de WhatsApp por el mismo camino sería: abrir el grupo, pegar texto
y foto, enviar.

Antes de construirlo hay que saber:

- **Riesgo de baneo:** automatizar la app de WhatsApp va contra sus términos. Manejar la app
  real por la pantalla, desde el número de Lanny, a ritmo humano y solo en su propio grupo es
  bastante más discreto que una librería tipo whatsapp-web.js, pero el riesgo no es cero.
  Perder el número de Lanny cuesta más que lo que hoy deja el grupo (R$ 20 a 70 por mes).
- **¿De qué celular sale?** El A07 conectado es el de Nick. Si el grupo es de Lanny, o el
  número de Nick pasa a ser admin y publica él, o hay que conectar el celular de Lanny.
- **Paso intermedio sugerido:** primero que el bot arme la cola del día (26 a 28 posts con link
  de Lanny, foto y horario, siguiendo el plan de rubros) y la deje lista; el envío puede
  seguir siendo de un toque. Cuando la cola funcione sola varios días, recién ahí automatizar
  el último toque.
- **Medición:** cada envío debería quedar registrado (producto, hora). Hoy no se sabe qué
  llegó al grupo, y sin eso no se puede atar qué post vendió.

## 6. Mejoras, en orden de impacto

1. **Envío constante todos los días, de lunes a sábado.** El dato más fuerte del análisis es
   el hueco de 19 días sin ventas. Una cola diaria armada por el bot (con link de Lanny ya
   generado) resuelve la constancia aunque el envío siga siendo manual.
2. **2 por hora fijo, de 8 h a 21 h**, con los productos más fuertes del día en el tramo de
   15 h a 20 h, donde cae casi la mitad de los clics y la compra es en los 25 minutos
   siguientes.
3. **80 % hogar y 20 % rubro del día**, coherente con cómo Lanny promociona el grupo.
4. **Priorizar productos de R$ 20 a R$ 50 con comisión de 8 % o más.** Las ventas recientes
   son de 3 a 4 % y dejan R$ 1 cada una; las de septiembre de 10 a 18 % dejaban R$ 4 a R$ 17.
5. **Registrar cada envío** (producto, hora, rubro) para poder medir el plan en 30 días.
6. **Formato del post:** en el grupo van posts (foto y texto), no videos, así que la foto
   tiene que mostrar el producto claro. Corto, precio "De/Por" y el link arriba, porque la
   compra es impulsiva. No se pudo medir el formato actual sin leer el canal; queda para cuando haya
   registro de envíos.

## Las 3 mejoras que recomiendo primero

1. **Cola diaria armada por el bot**, de lunes a sábado, siguiendo tu plan de rubros, con el
   link de Lanny ya generado y registro de cada envío. Ataca el problema real (el corte de
   octubre) sin riesgo para el número.
2. **2 productos por hora fijo**, de 8 h a 21 h (26 a 28 por día), con lo más fuerte del
   día entre 15 h y 20 h.
3. **80 % hogar y 20 % rubro del día**, prefiriendo comisión de 8 % o más, y revisando a los
   30 días contra las ventas con `referrer` WhatsApp qué parte vino de cada lado.

Lo que no se pudo medir: qué copia Lanny realmente al grupo, el rubro y el formato de lo que
publica el bot, las ventas de Mercado Livre, y cuántas personas tiene el grupo.
