"""Prueba, contra la base real del panel, que un usuario que no es admin ve solo
sus cuentas y marca como publicados solo sus videos. No se da por bueno leyendo
las politicas: se entra como un usuario de verdad y se mira que devuelve la base.

Crea un usuario temporal, dos cuentas temporales (`prueba`, suya, y `prueba2`, de
nadie) con una venta y tres videos, mira que puede hacer ese usuario y despues
borra SOLO lo que creo (aunque algo falle en el medio). No toca `lanny` ni `nick`.

Uso (desde la raiz del bot):
    python scripts/verificar_acceso_panel.py
"""

import os
import secrets
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(_RAIZ / ".env")

URL = os.environ["SUPABASE_PANEL_URL"].rstrip("/")
SERVICIO = os.environ["SUPABASE_PANEL_SERVICE_KEY"]
ANON = os.environ["SUPABASE_PANEL_ANON_KEY"]

_ADMIN = {"apikey": SERVICIO, "Authorization": f"Bearer {SERVICIO}",
          "Content-Type": "application/json"}

_VENTA = {"cuenta": "prueba", "conversion_id": 1, "order_id": "PRUEBA", "item_id": 1,
          "model_id": 0, "compra_en": "2026-10-02T12:00:00+00:00", "estado": "PENDING",
          "producto": "Venta de prueba", "precio": 1, "cantidad": 1, "comision": 0.1,
          "origen": "prueba", "vista_en": "2026-10-02T12:00:00+00:00"}

_GRABADO = "2026-10-01T12:00:00+00:00"
_VIDEOS = [
    # 1: suyo, sin publicar. 2: suyo, ya confirmado por la PC. 3: ajeno.
    {"canal": "prueba", "item_id": 1, "cuenta": "prueba", "grabado_en": _GRABADO,
     "publicado_en": None},
    {"canal": "prueba", "item_id": 2, "cuenta": "prueba", "grabado_en": _GRABADO,
     "publicado_en": _GRABADO},
    {"canal": "prueba2", "item_id": 3, "cuenta": "prueba2", "grabado_en": _GRABADO,
     "publicado_en": None},
]

# Lo mismo que hace el panel: si la marca ya existe, no hacer nada.
_MARCAR = f"{URL}/rest/v1/publicacao?on_conflict=canal,item_id"


def _ok(r: requests.Response, que: str) -> requests.Response:
    if r.status_code >= 300:
        raise RuntimeError(f"{que}: {r.status_code} {r.text[:200]}")
    return r


def _usuario(token: str | None) -> dict:
    return {"apikey": ANON, "Authorization": f"Bearer {token or ANON}",
            "Content-Type": "application/json"}


def _leer(tabla: str, token: str | None) -> list[dict]:
    return _ok(requests.get(f"{URL}/rest/v1/{tabla}?select=*", headers=_usuario(token),
                            timeout=30), f"leer {tabla}").json()


def _marcar(token: str | None, canal: str, item_id: int) -> requests.Response:
    return requests.post(_MARCAR, json={"canal": canal, "item_id": item_id}, timeout=30,
                         headers={**_usuario(token),
                                  "Prefer": "resolution=ignore-duplicates,return=minimal"})


def _marcas(canal: str, item_id: int) -> list[dict]:
    """Las marcas de un video, leidas con la llave de servicio (sin RLS)."""
    return _ok(requests.get(
        f"{URL}/rest/v1/publicacao?canal=eq.{canal}&item_id=eq.{item_id}&select=*",
        headers=_ADMIN, timeout=30), "leer marcas").json()


def _desmarcar(token: str, canal: str, item_id: int) -> None:
    # La RLS no da error al borrar algo que no le corresponde: simplemente no lo
    # borra. Por eso despues se mira con la llave de servicio si la fila sigue.
    requests.delete(f"{URL}/rest/v1/publicacao?canal=eq.{canal}&item_id=eq.{item_id}",
                    headers=_usuario(token), timeout=30)


def main() -> int:
    email = f"verificacion-{secrets.token_hex(4)}@panel.test"
    clave = secrets.token_urlsafe(24)
    usuario = None
    resultados: list[tuple[str, bool]] = []
    try:
        usuario = _ok(requests.post(f"{URL}/auth/v1/admin/users", headers=_ADMIN, timeout=30,
                                    json={"email": email, "password": clave, "email_confirm": True}),
                      "crear usuario").json()["id"]
        token = _ok(requests.post(f"{URL}/auth/v1/token?grant_type=password", timeout=30,
                                  headers={"apikey": ANON, "Content-Type": "application/json"},
                                  json={"email": email, "password": clave}),
                    "iniciar sesion").json()["access_token"]

        resultados.append(("usuario sin cuenta no ve ventas", _leer("venta", token) == []))

        _ok(requests.post(f"{URL}/rest/v1/cuenta", headers=_ADMIN, timeout=30,
                          json=[{"id": "prueba", "nombre": "Prueba", "dueno": usuario},
                                {"id": "prueba2", "nombre": "Prueba 2", "dueno": None}]), "crear cuentas")
        _ok(requests.post(f"{URL}/rest/v1/venta", headers=_ADMIN, timeout=30, json=_VENTA),
            "crear venta")
        _ok(requests.post(f"{URL}/rest/v1/video", headers=_ADMIN, timeout=30, json=_VIDEOS),
            "crear videos")

        ventas = _leer("venta", token)
        resultados.append(("ve solo la venta de su cuenta",
                           len(ventas) == 1 and ventas[0]["cuenta"] == "prueba"))
        resultados.append(("ve solo sus videos",
                           sorted(v["item_id"] for v in _leer("video", token)) == [1, 2]))
        resultados.append(("ve solo su cuenta",
                           [c["id"] for c in _leer("cuenta", token)] == ["prueba"]))
        # Sin login la base ni siquiera da permiso de leer la tabla (anon no tiene
        # grant): un 401/403 es la respuesta correcta, igual que una lista vacia.
        sin_login = requests.get(f"{URL}/rest/v1/venta?select=*", timeout=30,
                                 headers=_usuario(None))
        resultados.append(("sin login no ve ventas", sin_login.status_code in (401, 403)
                           or (sin_login.status_code == 200 and sin_login.json() == [])))

        # --- Marcas de publicado (etapa 2) ---
        r = _marcar(token, "prueba", 1)
        resultados.append(("marca su video", r.status_code < 300
                           and _marcas("prueba", 1)[0]["marcado_por"] == usuario))
        r = _marcar(token, "prueba", 1)
        resultados.append(("marcar dos veces no falla ni duplica",
                           r.status_code < 300 and len(_marcas("prueba", 1)) == 1))
        resultados.append(("no marca un video ajeno",
                           _marcar(token, "prueba2", 3).status_code >= 400
                           and _marcas("prueba2", 3) == []))
        resultados.append(("sin login no marca",
                           _marcar(None, "prueba", 2).status_code >= 400
                           and _marcas("prueba", 2) == []))

        _ok(requests.post(f"{URL}/rest/v1/publicacao", headers=_ADMIN, timeout=30,
                          json=[{"canal": "prueba", "item_id": 2, "marcado_por": usuario},
                                {"canal": "prueba2", "item_id": 3, "marcado_por": usuario}]),
            "crear marcas con servicio")
        _desmarcar(token, "prueba", 2)
        resultados.append(("no desmarca uno ya confirmado", len(_marcas("prueba", 2)) == 1))
        _desmarcar(token, "prueba2", 3)
        resultados.append(("no desmarca uno ajeno", len(_marcas("prueba2", 3)) == 1))
        _desmarcar(token, "prueba", 1)
        resultados.append(("desmarca uno suyo sin confirmar", _marcas("prueba", 1) == []))
    finally:
        limpieza = True
        for que, url in (
            ("borrar marcas", f"{URL}/rest/v1/publicacao?canal=in.(prueba,prueba2)"),
            ("borrar videos", f"{URL}/rest/v1/video?cuenta=in.(prueba,prueba2)"),
            ("borrar venta", f"{URL}/rest/v1/venta?cuenta=eq.prueba"),
            ("borrar cuentas", f"{URL}/rest/v1/cuenta?id=in.(prueba,prueba2)"),
        ):
            if requests.delete(url, headers=_ADMIN, timeout=30).status_code >= 300:
                print(f"OJO, no pude {que}")
                limpieza = False
        if usuario and requests.delete(f"{URL}/auth/v1/admin/users/{usuario}", headers=_ADMIN,
                                       timeout=30).status_code >= 300:
            print(f"OJO, no pude borrar el usuario {email}")
            limpieza = False
        print("limpieza ok" if limpieza else "limpieza INCOMPLETA")

    for nombre, paso in resultados:
        print(f"{'PASS' if paso else 'FAIL'}  {nombre}")
    esperados = 12
    return 0 if len(resultados) == esperados and all(p for _, p in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
