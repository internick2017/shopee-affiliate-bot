"""El adaptador copiado de home-office-br: solo lo que cambio al copiarlo."""

from src.canal_youtube import CATEGORIA_ESTILO, hacer_publico, subir_short


class Resp:
    def __init__(self, status, headers=None, cuerpo=None):
        self.status_code, self.headers, self._cuerpo = status, headers or {}, cuerpo

    def json(self):
        return self._cuerpo


def test_subir_short_usa_la_categoria_pedida(tmp_path):
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"x")
    enviado = {}

    def post(url, **kw):
        enviado.update(kw["json"])
        return Resp(200, {"Location": "https://subida"})

    vid = subir_short(str(mp4), "t", "d", "tok", privado=True, categoria=CATEGORIA_ESTILO,
                      http_post=post, http_put=lambda url, **kw: Resp(200, cuerpo={"id": "V1"}))

    assert vid == "V1"
    assert enviado["snippet"]["categoryId"] == "26"
    assert enviado["status"]["privacyStatus"] == "private"


def test_hacer_publico_manda_el_status_completo():
    enviado = {}

    def put(url, **kw):
        enviado.update(url=url, **kw["json"])
        return Resp(200)

    assert hacer_publico("V1", "tok", http_put=put)
    assert enviado["url"].endswith("part=status")
    assert enviado["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    assert not hacer_publico("V1", "tok", http_put=lambda *a, **k: Resp(403))
