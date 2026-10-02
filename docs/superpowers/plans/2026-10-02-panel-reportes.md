# Panel de reportes de afiliados (etapa 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un panel web, abierto desde el celular con usuario para Nick y Lanny, que muestra las ventas de afiliado de Shopee de las dos cuentas y qué video vendió, alimentado por un sincronizador que corre en la PC de Nick.

**Architecture:** `sync_panel.py` (repo del bot) lee la API de Shopee de cada cuenta y `grabados.db`, y hace upsert en un proyecto nuevo de Supabase por PostgREST con la llave de servicio. El panel (repo nuevo, Next.js en Vercel) lee de Supabase con la llave pública; Row Level Security decide qué filas ve cada usuario.

**Tech Stack:** Python 3.12 + requests + pytest (bot); Supabase (Postgres, Auth, RLS); Next.js 16.3.3 + React 19.1.0 + @supabase/supabase-js + vitest (panel), dependencias con yarn.

**Spec:** `docs/superpowers/specs/2026-10-02-panel-reportes-design.md` (repo del bot).

## Global Constraints

- Las claves de Shopee y `SUPABASE_PANEL_SERVICE_KEY` viven solo en el `.env` del bot; nunca en el repo del panel, en Vercel ni en un log.
- Variables del `.env` del bot: `SUPABASE_PANEL_URL`, `SUPABASE_PANEL_SERVICE_KEY`, `SUPABASE_PANEL_ANON_KEY`. Shopee: `SHOPEE_APP_ID`/`SHOPEE_SECRET` (cuenta `lanny`), `SHOPEE_APP_ID_NICK`/`SHOPEE_SECRET_NICK` (cuenta `nick`).
- Cargar el `.env` con ruta explícita (`load_dotenv(Path(__file__).parent / ".env")`): `load_dotenv()` pelado ya dio un falso `Invalid Credential` desde otro directorio.
- Nunca se borra una fila de `venta`. El panel no escribe nada.
- Cuenta de cada canal de video: `lanny` a `lanny`; `nick` y `setupjusto` a `nick`.
- Ventana de lectura de Shopee: últimos 90 días, todas las páginas (`limit:500`, `scrollId`).
- Meses y "hoy" en zona `America/Sao_Paulo`, no UTC.
- Plata en formato brasileño: `R$ 1.234,56`. Origen `Shopeevideo-Shopee` se muestra "Shopee Video".
- Textos del panel en portugués de Brasil (lo usa Lanny). Prosa sin guiones largos ni flechas.
- Panel: yarn, nunca npm/npx (rotos en la máquina de Nick); binarios por `./node_modules/.bin/*`.
- Commits sin `Co-Authored-By` ni mención de IA. Commitear solo con OK de Nick por tarea.
- Las cuentas (Supabase, Vercel, GitHub) las crea Nick; ningún secreto pasa por el chat.

## Review Focus

1. `completeTime` de una venta pendiente viene `0`, no null: tiene que quedar `completada_en = null`, no 1970. Test en Task 2.
2. La API devuelve `None` en la página 2 (rate limit 10030): las filas de la página 1 se escriben, pero la corrida de esa cuenta queda `ok = false` con el error. Test en Task 3.
3. Una cuenta sin ventas en 90 días (Nick casi): corrida `ok = true`, `filas = 0`; el panel muestra ceros, no error. Tests en Task 3 y Task 6.
4. Venta del 31 a las 22:00 de Brasil (01:00 UTC del día 1): cuenta en el mes del 31. Test en Task 6.
5. Usuario logueado sin cuenta asignada (Lanny antes de setear `dueno`): ve listas vacías y un aviso, no una pantalla rota. Verificado en Task 4 (RLS) y Task 7 (pantalla).

---

## Archivos

Repo del bot (`E:\dev\07-tools-personal\shopee-affiliate-bot`):
- Create `src/panel_sync.py`: transformar (puro) y escribir (PostgREST) + `sincronizar()`.
- Create `sync_panel.py`: entrypoint, carga `.env`, logging a `logs/sync_panel.log`.
- Create `scripts/verificar_acceso_panel.py`: prueba real de RLS con un usuario temporal.
- Create `tests/test_panel_sync.py`.
- Modify `instalar-tareas.ps1`: tarea `ShopeePanelSync` cada 4 h.

Repo nuevo del panel (`E:\dev\01-web-apps\panel-afiliados`):
- `supabase/migrations/0001_panel.sql`: tablas, RLS, filas de `cuenta`.
- `lib/supabase.ts`: cliente con `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- `lib/datos.ts`: lectura de tablas, tipos `Venta`, `Video`, `Sincronizacion`, `Cuenta`.
- `lib/calculos.ts` + `lib/calculos.test.ts`: agregados puros y formato.
- `app/login/page.tsx`, `app/(panel)/layout.tsx` (selector + pestañas + guardia de sesión), `app/(panel)/page.tsx` (Início), `app/(panel)/vendas/page.tsx`, `app/(panel)/origem/page.tsx`, `app/(panel)/videos/page.tsx`.

---

### Task 1: Esquema de Supabase y reglas de acceso

**Files:**
- Create: `E:\dev\01-web-apps\panel-afiliados\supabase\migrations\0001_panel.sql`
- Create: `E:\dev\01-web-apps\panel-afiliados\README.md` (qué es, cómo se aplica la migración, variables)

**Interfaces:**
- Produces: tablas `cuenta(id text pk, nombre text, dueno uuid null references auth.users)`, `perfil(usuario uuid pk references auth.users, es_admin boolean not null default false)`, `venta`, `video`, `sincronizacion` con las columnas exactas de la sección "Datos" del spec. PK de `venta`: `(cuenta, conversion_id, order_id, item_id, model_id)` con `model_id bigint not null default 0`. PK de `video`: `(canal, item_id)`. Función `es_admin() returns boolean` (security definer, lee `perfil` de `auth.uid()`).

- [ ] **Step 1: `git init` del repo del panel y escribir la migración**

  Contenido que el spec fija: `insert into cuenta (id, nombre) values ('lanny','Lanny'),('nick','Nick')`. RLS activado en las cinco tablas. Políticas solo `for select to authenticated`:
  - `cuenta`: `es_admin() or dueno = auth.uid()`.
  - `venta`, `video`: `es_admin() or cuenta in (select id from cuenta where dueno = auth.uid())`.
  - `sincronizacion`: lo mismo, más `or cuenta is null`.
  - `perfil`: `usuario = auth.uid()`.
  Ninguna política de insert/update/delete: solo la llave de servicio escribe. Índices: `venta(cuenta, compra_en desc)`, `video(cuenta)`.

- [ ] **Step 2: Checkpoint con Nick**

  Nick crea el proyecto de Supabase, pega el SQL en el SQL Editor y lo corre, y pone las tres variables `SUPABASE_PANEL_*` en el `.env` del bot. Verificación (sin mostrar la llave):
  Run: `python -c "from pathlib import Path; from dotenv import dotenv_values as d; v=d(Path('.env')); print([k for k in ('SUPABASE_PANEL_URL','SUPABASE_PANEL_SERVICE_KEY','SUPABASE_PANEL_ANON_KEY') if not v.get(k)])"` en el repo del bot.
  Expected: `[]`

- [ ] **Step 3: Verificar que la base responde y está vacía**

  Run: `GET {SUPABASE_PANEL_URL}/rest/v1/cuenta?select=id` con la llave de servicio (script de una línea con requests, imprime solo el JSON).
  Expected: `[{"id":"lanny"},{"id":"nick"}]`. Con la llave anon y sin login: `[]`.

- [ ] **Step 4: Commit** (repo del panel)

```bash
git add supabase/migrations/0001_panel.sql README.md
git commit -m "feat: esquema del panel con reglas de acceso por cuenta"
```

### Task 2: Transformar la respuesta de Shopee y la tabla de videos (puro)

**Files:**
- Create: `src/panel_sync.py`
- Test: `tests/test_panel_sync.py`

**Interfaces:**
- Produces:
  - `filas_de_ventas(cuenta: str, nodos: list[dict], *, vista_en: datetime) -> list[dict]`: una fila por item, claves exactas de las columnas de `venta`, fechas como ISO 8601 UTC.
  - `filas_de_videos(videos: list[VideoProducido]) -> list[dict]`: columnas de `video`.
  - `CUENTA_DE_CANAL: dict[str, str] = {"lanny": "lanny", "nick": "nick", "setupjusto": "nick"}`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_una_fila_por_item_con_la_clave_completa(): ...
    # 1 nodo, 1 orden, 2 items -> 2 filas; cada una con cuenta, conversion_id, order_id, item_id, model_id
def test_completeTime_cero_queda_null():
    fila = filas_de_ventas("nick", [_nodo(completeTime=0)], vista_en=_T)[0]
    assert fila["completada_en"] is None
def test_numeros_que_vienen_como_texto():
    fila = filas_de_ventas("lanny", [_nodo(itemPrice="28.99", qty=2, itemTotalCommission="1.7394")], vista_en=_T)[0]
    assert (fila["precio"], fila["cantidad"], fila["comision"]) == (28.99, 2, 1.7394)
def test_qty_ausente_vale_uno(): ...
def test_model_id_ausente_vale_cero(): ...
def test_referrer_vacio_queda_desconocido():
    assert filas_de_ventas("lanny", [_nodo(referrer=None)], vista_en=_T)[0]["origen"] == "desconocido"
def test_fechas_en_utc_iso():
    fila = filas_de_ventas("nick", [_nodo(purchaseTime=1790774580)], vista_en=_T)[0]
    assert fila["compra_en"] == "2026-09-30T13:23:00+00:00"
def test_setupjusto_va_a_la_cuenta_nick():
    assert filas_de_videos([_video(canal="setupjusto")])[0]["cuenta"] == "nick"
def test_video_sin_publicar_tiene_publicado_en_null(): ...
```

  `_nodo(**campos)` arma un nodo con `orders[0].items[0]`; los campos de conversión (`purchaseTime`, `clickTime`, `referrer`, `utmContent`, `conversionId`) van al nodo y los de item al item. `_T = datetime(2026, 10, 2, tzinfo=UTC)`.

- [ ] **Step 2: Correr y ver que fallan**

  Run: `python -m pytest tests/test_panel_sync.py -v`
  Expected: FAIL, `ModuleNotFoundError: src.panel_sync`

- [ ] **Step 3: Implementar las dos funciones**

  Mapeo de campos según la tabla "venta" del spec. `orderId` es string en Shopee: guardar como text. `categoria` = `categoryLv1Name`.

- [ ] **Step 4: Correr y ver que pasan, más ruff y mypy**

  Run: `python -m pytest tests/test_panel_sync.py -v && ruff check src/panel_sync.py && mypy`
  Expected: todo PASS, sin avisos.

- [ ] **Step 5: Commit**

```bash
git add src/panel_sync.py tests/test_panel_sync.py
git commit -m "feat(panel): convertir ventas de Shopee y videos a filas del panel"
```

### Task 3: Leer Shopee paginado, escribir en Supabase y el entrypoint

**Files:**
- Modify: `src/panel_sync.py`
- Create: `sync_panel.py`
- Test: `tests/test_panel_sync.py`

**Interfaces:**
- Consumes: `filas_de_ventas`, `filas_de_videos` (Task 2); `_graphql_call(app_id, secret, query, *, http_post)` de `src/shopee_resolver.py`; `VideosStore(db).listar(cuantos=100_000)`.
- Produces:
  - `leer_conversiones(app_id: str, secret: str, *, desde: int, hasta: int, http_post=...) -> tuple[list[dict], str | None]`: nodos de todas las páginas y el error (None si salió bien). Si una página falla devuelve lo leído hasta ahí y el error.
  - `class Supabase(url: str, llave: str, *, http=requests)` con `upsert(tabla: str, filas: list[dict], conflicto: str) -> None` (lanza `RuntimeError` con el status y el cuerpo, sin la llave) y `registrar(cuenta: str | None, empezo: datetime, ok: bool, filas: int, error: str | None) -> None`.
  - `sincronizar(cuentas: dict[str, tuple[str, str]], videos: list[VideoProducido], db: Supabase, *, ahora: datetime, http_post=...) -> dict[str, bool]`: resultado por cuenta y `"videos"`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_recorre_todas_las_paginas():
    # pagina 1: hasNextPage True, scrollId "abc"; pagina 2: hasNextPage False
    nodos, error = leer_conversiones("a", "s", desde=0, hasta=1, http_post=post)
    assert len(nodos) == 2 and error is None
    assert 'scrollId:"abc"' in consultas[1]
def test_pagina_que_falla_devuelve_lo_leido_y_el_error():
    nodos, error = leer_conversiones(..., http_post=post_que_falla_en_la_2)
    assert len(nodos) == 1 and error
def test_upsert_manda_merge_y_on_conflict():
    # FakeHttp captura la llamada
    db.upsert("venta", [{"x": 1}], "cuenta,conversion_id,order_id,item_id,model_id")
    assert http.url.endswith("/rest/v1/venta?on_conflict=cuenta,conversion_id,order_id,item_id,model_id")
    assert "resolution=merge-duplicates" in http.headers["Prefer"]
def test_error_de_supabase_no_incluye_la_llave():
    with pytest.raises(RuntimeError) as e: ...
    assert "LLAVE-SECRETA" not in str(e.value)
def test_una_cuenta_que_falla_no_frena_a_la_otra():
    r = sincronizar({"lanny": ("x", "y"), "nick": ("a", "b")}, [], db, ahora=_T, http_post=falla_solo_lanny)
    assert r == {"lanny": False, "nick": True, "videos": True}
    assert db.registros[0]["ok"] is False and db.registros[0]["error"]
def test_cuenta_sin_ventas_registra_ok_con_cero_filas(): ...
def test_ventana_de_90_dias():
    # la primera consulta lleva purchaseTimeStart = ahora - 90*86400
```

  `FakeSupabase` en el test: guarda `upserts` y `registros` en listas, misma firma que `Supabase`.

- [ ] **Step 2: Correr y ver que fallan**

  Run: `python -m pytest tests/test_panel_sync.py -v`
  Expected: FAIL en los tests nuevos (`ImportError`).

- [ ] **Step 3: Implementar**

  - Consulta: `conversionReport(purchaseTimeStart:%d,purchaseTimeEnd:%d,limit:500[,scrollId:"%s"])` con los campos de nodo `clickTime purchaseTime conversionId referrer utmContent` y de item `itemId modelId itemName itemPrice qty itemTotalCommission displayItemStatus completeTime imageUrl categoryLv1Name`, más `orders{orderId ...}` y `pageInfo{hasNextPage scrollId}`. Pausa de 1,5 s entre páginas (rate limit, igual que `run_snapshot.py`).
  - PostgREST: `POST {url}/rest/v1/{tabla}?on_conflict={conflicto}`, headers `apikey`, `Authorization: Bearer`, `Prefer: resolution=merge-duplicates,return=minimal`; lotes de 500 filas.
  - `sincronizar`: por cuenta, `try` alrededor de leer + upsert; `registrar` siempre, también si falló. Videos después, igual.
  - `sync_panel.py`: `load_dotenv(Path(__file__).parent / ".env")`; `configurar_logging("sync-panel", "logs/sync_panel.log")`; si falta alguna `SUPABASE_PANEL_*`, log de error y `sys.exit(2)` antes de llamar a Shopee; al final un log por cuenta con filas y ok; exit 1 si alguna falló.

- [ ] **Step 4: Correr tests, ruff y mypy**

  Run: `python -m pytest -q && ruff check . && mypy`
  Expected: todo verde (incluidos los tests viejos del bot).

- [ ] **Step 5: Corrida real contra Supabase**

  Run: `python sync_panel.py`
  Expected: exit 0; log con `lanny` y `nick` ok. Comprobar con un `GET /rest/v1/venta?select=count` por cuenta (llave de servicio) que hay filas; los completados de Lanny de los últimos 30 días suman R$ 109,60 aprox. (cifra del 2026-10-02; puede haber cambiado si se completaron pendientes, en ese caso explicar la diferencia). Correr `python sync_panel.py` otra vez y confirmar que el conteo no cambió (no duplica).

- [ ] **Step 6: Commit**

```bash
git add src/panel_sync.py sync_panel.py tests/test_panel_sync.py
git commit -m "feat(panel): sincronizar ventas y videos a Supabase"
```

### Task 4: Prueba real de quién ve qué

**Files:**
- Create: `scripts/verificar_acceso_panel.py`

**Interfaces:**
- Consumes: `Supabase` (Task 3) para preparar y limpiar.

- [ ] **Step 1: Escribir el script**

  Con la API admin de Supabase Auth (`POST /auth/v1/admin/users`, llave de servicio) crea un usuario temporal `verificacion-<aleatorio>@panel.test` con contraseña aleatoria, crea la cuenta temporal `prueba` con `dueno` = ese usuario y una fila de `venta` en ella. Inicia sesión como ese usuario (`POST /auth/v1/token?grant_type=password`, llave anon) y consulta `venta`, `video`, `cuenta`, `sincronizacion`. Después, en un `finally`, borra la fila de `venta` de `prueba`, la cuenta `prueba` y el usuario. Es la única escritura de borrado del plan y solo toca lo que el script creó.

  Asserts que imprime como PASS/FAIL:
  - `venta` devuelve solo filas de `prueba` (1 fila), ninguna de `lanny` ni `nick`.
  - `video` devuelve 0 filas.
  - `cuenta` devuelve solo `prueba`.
  - Con la llave anon y sin login, `venta` devuelve `[]`.
  - Con el usuario sin cuenta (antes de asignarle `prueba`), `venta` devuelve `[]` y no un error.

- [ ] **Step 2: Correrlo**

  Run: `python scripts/verificar_acceso_panel.py`
  Expected: 5 PASS, y al final `limpieza ok`. Confirmar en Supabase (Auth > Users) que no quedó el usuario temporal.

- [ ] **Step 3: Commit**

```bash
git add scripts/verificar_acceso_panel.py
git commit -m "test(panel): verificar contra la base real que cada usuario ve solo lo suyo"
```

### Task 5: Tarea programada cada 4 horas

**Files:**
- Modify: `instalar-tareas.ps1`

- [ ] **Step 1: Agregar la tarea `ShopeePanelSync`**

  Separada del arreglo `$tareas` de los bots (esas son procesos eternos con reintento cada 2 min; esta termina sola). Disparador `-Once -At (Get-Date).AddMinutes(-1)` con `RepetitionInterval` de 4 h y `Duration = $null` (misma trampa documentada en el script), `ExecutionTimeLimit` de 30 min, `MultipleInstances IgnoreNew`, `StartWhenAvailable` (si la PC estaba apagada, corre al prenderla), `pythonw.exe sync_panel.py`. `-Desinstalar` también la borra. Comentario breve con el porqué de cada diferencia.

- [ ] **Step 2: Instalar y disparar**

  Run: `powershell -ExecutionPolicy Bypass -File instalar-tareas.ps1` y después `Start-ScheduledTask -TaskName ShopeePanelSync`.
  Expected: `Get-ScheduledTaskInfo ShopeePanelSync` con `LastTaskResult 0` y `NextRunTime` dentro de 4 h; `logs/sync_panel.log` con la corrida nueva. Los bots siguen vivos (`Get-ScheduledTask ShopeeBot*` en `Running`).

- [ ] **Step 3: Commit**

```bash
git add instalar-tareas.ps1
git commit -m "feat(panel): tarea programada que sincroniza el panel cada 4 horas"
```

### Task 6: Panel base: login, datos y cálculos

**Files:**
- Create (repo del panel): `package.json`, `tsconfig.json`, `next.config.mjs`, `.gitignore`, `.env.local.example`, `lib/supabase.ts`, `lib/datos.ts`, `lib/calculos.ts`, `lib/calculos.test.ts`, `app/layout.tsx`, `app/login/page.tsx`, `app/(panel)/layout.tsx`

**Interfaces:**
- Consumes: tablas de Task 1.
- Produces (`lib/calculos.ts`):
  - `mesDe(fechaIso: string): string` devuelve `"2026-09"` en zona `America/Sao_Paulo`.
  - `resumenDelMes(ventas: Venta[], mes: string): { completada: number; pendiente: number; cancelada: number }` (comisión).
  - `porMes(ventas: Venta[]): { mes: string; completada: number; pendiente: number }[]` ordenado ascendente.
  - `porOrigen(ventas: Venta[]): { origen: string; ventas: number; comision: number; tasaPct: number }[]` sin canceladas, `tasaPct = 100 * comision / sum(precio * cantidad)`, orden por ventas desc.
  - `nombreOrigen(crudo: string): string` (`Shopeevideo-Shopee` a `Shopee Video`).
  - `reais(n: number): string` (`R$ 1.234,56`).
  - `haceCuanto(iso: string, ahora: Date): string` ("há 2 h", "há 3 dias").
- Produces (`app/(panel)/layout.tsx`): contexto `useCuenta(): { cuenta: "lanny" | "nick" | "todo"; esAdmin: boolean; cuentas: Cuenta[] }`.

- [ ] **Step 1: Scaffold** con `yarn init -y` y `yarn add next@16.3.3 react@19.1.0 react-dom@19.1.0 @supabase/supabase-js` y `yarn add -D typescript @types/react @types/node vitest`. Scripts `dev`, `build`, `test` (`vitest run`). `.env.local` (no commiteado) con `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY`, copiados del `.env` del bot por Nick o por un script que no imprime valores.

- [ ] **Step 2: Escribir los tests que fallan** (`lib/calculos.test.ts`)

```ts
test("venta del 31 a las 22:00 de Brasil cuenta en ese mes", () => {
  expect(mesDe("2026-11-01T01:00:00+00:00")).toBe("2026-10");
});
test("resumen separa completada, pendiente y cancelada", ...);
test("cuenta sin ventas da ceros", () => {
  expect(resumenDelMes([], "2026-10")).toEqual({ completada: 0, pendiente: 0, cancelada: 0 });
});
test("porOrigen excluye canceladas y calcula la tasa", () => {
  // 2 ventas WhatsApp: precio 100 x1 comision 10, cancelada precio 50 comision 5
  expect(porOrigen(v)[0]).toMatchObject({ origen: "WhatsApp", ventas: 1, comision: 10, tasaPct: 10 });
});
test("Shopee Video con nombre legible", () => expect(nombreOrigen("Shopeevideo-Shopee")).toBe("Shopee Video"));
test("reais en formato brasileño", () => expect(reais(1234.56)).toBe("R$ 1.234,56"));
```

- [ ] **Step 3: Correr y ver que fallan**: `./node_modules/.bin/vitest run`, Expected FAIL (módulo no existe).

- [ ] **Step 4: Implementar `lib/calculos.ts`, `lib/supabase.ts`, `lib/datos.ts`** (lecturas: `ventas(cuenta)`, `videos(cuenta)`, `ultimasSincronizaciones()`, `perfil()`, `cuentas()`; con `cuenta = "todo"` no filtra y RLS decide), y la página de login (email + senha, `signInWithPassword`, mensaje de error en portugués) y el layout `(panel)` (sin sesión redirige a `/login`; selector Lanny · Nick · Todo solo si `esAdmin`; si no es admin y no tiene cuenta, aviso "Sua conta ainda não está ligada a nenhuma loja"; barra de pestañas abajo: Início, Vendas, Origem, Vídeos; botón Sair).

- [ ] **Step 5: Verificar**: `./node_modules/.bin/vitest run` PASS; `./node_modules/.bin/tsc --noEmit` sin errores; `./node_modules/.bin/next build` OK.

- [ ] **Step 6: Commit** (repo del panel)

```bash
git add package.json yarn.lock tsconfig.json next.config.mjs .gitignore .env.local.example lib app
git commit -m "feat: login, selector de cuenta y cálculos del panel"
```

### Task 7: Las cuatro pantallas

**Files:**
- Create: `app/(panel)/page.tsx`, `app/(panel)/vendas/page.tsx`, `app/(panel)/origem/page.tsx`, `app/(panel)/videos/page.tsx`, `app/globals.css`

**Interfaces:**
- Consumes: `useCuenta`, `lib/datos.ts`, `lib/calculos.ts` (Task 6).

- [ ] **Step 1: Início**: tres tarjetas del mes (Concluída, Pendente, Cancelada) con diferencia contra el mes anterior; barras CSS de `porMes` (sin librería de gráficos); cartel "Atualizado há X" por cuenta, rojo si la última `sincronizacion` de esa cuenta tiene `ok = false`, con el error.
- [ ] **Step 2: Vendas**: lista por `compra_en` desc con foto (`imagen_url`, `loading="lazy"`), producto, comisión, chip de estado y origen; filtros por estado, origen y mes (selects).
- [ ] **Step 3: Origem**: tabla de `porOrigen`.
- [ ] **Step 4: Vídeos**: arriba "Para publicar" (videos con `publicado_en` null: archivo + link tocable); abajo, por video, ventas de su `item_id` en su cuenta (cantidad y comisión), y un total aparte de ventas con origen Shopee Video.
- [ ] **Step 5: Verificar con datos reales** en `yarn dev`, en el Browser pane con viewport mobile (375x812): las cuatro pantallas con la cuenta de Nick admin; totales de Início iguales a los de la base; sin scroll horizontal; `next build` OK. Volver el viewport a desktop.
- [ ] **Step 6: Commit**

```bash
git add app
git commit -m "feat: pantallas de inicio, ventas, origen y videos"
```

### Task 8: Publicar y crear los usuarios

- [ ] **Step 1: Checkpoint con Nick**: crea el repo en GitHub (o aprueba que lo cree con `gh repo create --private`), lo conecta a Vercel y carga en Vercel `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY`. En Supabase Auth > URL Configuration pone la URL de Vercel como Site URL.
- [ ] **Step 2: Push** (con OK de Nick) y esperar el deploy. Expected: la URL de Vercel muestra el login.
- [ ] **Step 3: Usuario de Nick**: Nick se registra/invita a sí mismo desde el dashboard de Supabase; con la llave de servicio, `perfil(usuario, es_admin=true)` y `cuenta nick.dueno = usuario`. Expected: entra desde el celular y ve Lanny · Nick · Todo.
- [ ] **Step 4: Usuario de Lanny**: con el email que pase Nick y su OK explícito, invitación por `POST /auth/v1/invite`. Al aceptarla, `cuenta lanny.dueno = usuario`, sin fila de admin. Expected: Lanny ve solo lo suyo, sin selector.
- [ ] **Step 5: Correr otra vez `scripts/verificar_acceso_panel.py`** con los usuarios reales ya creados. Expected: 5 PASS.
- [ ] **Step 6: Anotar** en la memoria del proyecto: URL del panel, que la sync corre como `ShopeePanelSync` y dónde están las variables.
