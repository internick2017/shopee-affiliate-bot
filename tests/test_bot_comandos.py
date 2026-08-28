"""El catalogo de comandos es UNA sola lista que alimenta tres cosas: el menu
nativo de Telegram (el que aparece al escribir "/"), el texto de /ayuda y el aviso
de comando desconocido. Si se separaran, se desincronizan y el menu miente."""

from src.bot_comandos import COMANDOS, comandos_para_telegram, texto_ayuda, texto_desconocido


def test_cada_comando_tiene_nombre_y_descripcion_utiles():
    assert COMANDOS
    for c in COMANDOS:
        assert c.nombre == c.nombre.lower()
        assert not c.nombre.startswith("/")      # Telegram lo quiere sin barra
        assert " " not in c.nombre
        assert c.descripcion
        # Telegram corta las descripciones del menu en 256 y rechaza las vacias.
        assert 1 <= len(c.descripcion) <= 256


def test_el_menu_de_telegram_sale_del_mismo_catalogo():
    pares = comandos_para_telegram()
    assert pares == [(c.nombre, c.descripcion) for c in COMANDOS]
    assert ("ventas", ) == (pares[[p[0] for p in pares].index("ventas")][0], )


def test_ayuda_lista_todos_los_comandos():
    t = texto_ayuda()
    for c in COMANDOS:
        assert f"/{c.nombre}" in t


def test_desconocido_nombra_el_comando_y_ofrece_ayuda():
    t = texto_desconocido("/ventaz")
    assert "/ventaz" in t
    assert "/ayuda" in t


def test_desconocido_escapa_lo_que_escribio_el_usuario():
    """El mensaje va con parse_mode=HTML y el texto lo escribe una persona."""
    t = texto_desconocido("/<b>x</b> & y")
    assert "&lt;b&gt;" in t
    assert "&amp;" in t
    assert "<b>x</b>" not in t


def test_desconocido_recorta_un_texto_absurdo():
    t = texto_desconocido("/" + "z" * 500)
    assert len(t) < 400


from src.bot_comandos import parece_comando


def test_parece_comando_agarra_el_caso_del_espacio():
    """EL caso real: Telegram no marca "/ ventas 90" como comando (no hay entidad
    bot_command), asi que filters.COMMAND no lo ve y cae en el handler de texto
    suelto. Hay que detectarlo a mano o el usuario recibe "no encontre ningun link"."""
    assert parece_comando("/ ventas 90")
    assert parece_comando("/ventaz")
    assert parece_comando("   /ideas limpeza")


def test_parece_comando_no_confunde_un_link_ni_texto_normal():
    assert not parece_comando("https://s.shopee.com.br/9AOBJUPs3Y")
    assert not parece_comando("hola, me armas el post?")
    assert not parece_comando("")
    assert not parece_comando(None)
    # Una fraccion o una fecha escritas al pasar no son un comando.
    assert not parece_comando("1/2 kilo")
