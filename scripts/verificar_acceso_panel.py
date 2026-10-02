"""Prueba, contra la base real del panel, que un usuario que no es admin ve solo
sus cuentas. No se da por bueno leyendo las politicas: se entra como un usuario
de verdad y se mira que devuelve la base.

Crea un usuario temporal y una cuenta temporal `prueba` con una venta, mira que ve
ese usuario y despues borra SOLO lo que creo (aunque algo falle en el medio).
No toca las cuentas `lanny` ni `nick`.

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


def _ok(r: requests.Response, que: str) -> requests.Response:
    if r.status_code >= 300:
        raise RuntimeError(f"{que}: {r.status_code} {r.text[:200]}")
    return r


def _leer(tabla: str, token: str | None) -> list[dict]:
    headers = {"apikey": ANON, "Authorization": f"Bearer {token or ANON}"}
    return _ok(requests.get(f"{URL}/rest/v1/{tabla}?select=*", headers=headers, timeout=30),
               f"leer {tabla}").json()


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
                          json={"id": "prueba", "nombre": "Prueba", "dueno": usuario}), "crear cuenta")
        _ok(requests.post(f"{URL}/rest/v1/venta", headers=_ADMIN, timeout=30, json=_VENTA),
            "crear venta")

        ventas = _leer("venta", token)
        resultados.append(("ve solo la venta de su cuenta",
                           len(ventas) == 1 and ventas[0]["cuenta"] == "prueba"))
        resultados.append(("no ve videos de otras cuentas", _leer("video", token) == []))
        resultados.append(("ve solo su cuenta",
                           [c["id"] for c in _leer("cuenta", token)] == ["prueba"]))
        # Sin login la base ni siquiera da permiso de leer la tabla (anon no tiene
        # grant): un 401/403 es la respuesta correcta, igual que una lista vacia.
        sin_login = requests.get(f"{URL}/rest/v1/venta?select=*", timeout=30,
                                 headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"})
        resultados.append(("sin login no ve ventas", sin_login.status_code in (401, 403)
                           or (sin_login.status_code == 200 and sin_login.json() == [])))
    finally:
        limpieza = True
        for que, url in (("borrar venta", f"{URL}/rest/v1/venta?cuenta=eq.prueba"),
                         ("borrar cuenta", f"{URL}/rest/v1/cuenta?id=eq.prueba")):
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
    return 0 if len(resultados) == 5 and all(p for _, p in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
