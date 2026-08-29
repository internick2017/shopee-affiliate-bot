"""Tests del logging a archivo.

Importa: con los bots corriendo ocultos (tarea programada, sin ventana), el log a
pantalla se pierde. Si un bot se reinicia solo, el archivo es la UNICA evidencia de
por que se cayo."""

import logging

import pytest

from src.logging_setup import configurar_logging


@pytest.fixture(autouse=True)
def _limpiar_root():
    """Cada test arranca con el root logger limpio y lo deja limpio."""
    previos = list(logging.getLogger().handlers)
    logging.getLogger().handlers = []
    yield
    for h in logging.getLogger().handlers:
        h.close()
    logging.getLogger().handlers = previos


def test_escribe_al_archivo_indicado(tmp_path):
    log = tmp_path / "sub" / "bot.log"
    logger = configurar_logging("probe", log)
    logger.info("hola mundo")
    for h in logging.getLogger().handlers:
        h.flush()

    assert log.exists(), "tiene que crear el archivo (y su carpeta)"
    assert "hola mundo" in log.read_text(encoding="utf-8")


def test_incluye_fecha_y_nivel(tmp_path):
    """Sin timestamp el log no sirve para saber CUANDO se reinicio."""
    log = tmp_path / "bot.log"
    configurar_logging("probe", log).warning("ojo")
    for h in logging.getLogger().handlers:
        h.flush()

    linea = log.read_text(encoding="utf-8").strip()
    assert "WARNING" in linea and "ojo" in linea
    assert linea[:4].isdigit(), f"esperaba que arranque con el año: {linea!r}"


def test_sigue_logueando_a_pantalla(tmp_path):
    """El archivo se SUMA a la consola, no la reemplaza: arrancar a mano y ver la
    ventana tiene que seguir funcionando."""
    configurar_logging("probe", tmp_path / "bot.log")
    tipos = [type(h).__name__ for h in logging.getLogger().handlers]
    assert "StreamHandler" in tipos
    assert "RotatingFileHandler" in tipos


def test_rota_y_no_crece_infinito(tmp_path):
    """Un bot 24/7 loguea para siempre; sin rotacion se come el disco."""
    log = tmp_path / "bot.log"
    configurar_logging("probe", log, max_bytes=1024, backups=2)
    logger = logging.getLogger("probe")
    for i in range(500):
        logger.info("linea de relleno numero %d con texto para ocupar lugar", i)

    assert log.stat().st_size <= 4096, "el archivo activo tiene que rotar"
    rotados = sorted(p.name for p in tmp_path.glob("bot.log.*"))
    assert rotados == ["bot.log.1", "bot.log.2"], f"backups inesperados: {rotados}"


def test_llamarlo_dos_veces_no_duplica_handlers(tmp_path):
    """Si se llama dos veces, cada linea saldria duplicada en el archivo."""
    log = tmp_path / "bot.log"
    configurar_logging("probe", log)
    configurar_logging("probe", log)
    logging.getLogger("probe").info("una sola vez")
    for h in logging.getLogger().handlers:
        h.flush()

    assert log.read_text(encoding="utf-8").count("una sola vez") == 1


def test_sin_consola_no_agrega_handler_de_pantalla(tmp_path, monkeypatch):
    """Bajo pythonw.exe lanzado por el Programador de tareas no hay consola y
    `sys.stderr` es None. Un StreamHandler ahi falla en CADA linea; hay que
    saltearlo y dejar solo el archivo."""
    monkeypatch.setattr("sys.stderr", None)
    monkeypatch.setattr("sys.stdout", None)
    log = tmp_path / "bot.log"

    logger = configurar_logging("probe", log)
    logger.info("sin consola")
    for h in logging.getLogger().handlers:
        h.flush()

    # Solo los handlers propios: pytest engancha los suyos al root logger.
    mios = [type(h).__name__ for h in logging.getLogger().handlers
            if getattr(h, "_bot_handler", False)]
    assert mios == ["RotatingFileHandler"], mios
    assert "sin consola" in log.read_text(encoding="utf-8")


def test_no_escribe_el_token_del_bot_al_archivo(tmp_path):
    """httpx loguea la URL completa de cada request y el token de Telegram va EN
    la URL. En pantalla se perdia; en un archivo queda el token en texto plano.
    Se bajan esos loggers a WARNING."""
    log = tmp_path / "bot.log"
    configurar_logging("probe", log)
    logging.getLogger("httpx").info(
        'HTTP Request: POST https://api.telegram.org/bot123:SECRETO/getMe "200 OK"'
    )
    for h in logging.getLogger().handlers:
        h.flush()

    contenido = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "SECRETO" not in contenido
