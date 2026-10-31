from src.grabados_store import IntentosStore


def test_el_informe_compara_ganchos_por_resultado(tmp_path):
    s = IntentosStore(tmp_path / "g.db")
    s.registrar("a", herramienta="Flow", prompt="p1", estado="generado", gancho="resultado")
    s.registrar("b", herramienta="Flow", prompt="p2", estado="generado", gancho="resultado")
    s.registrar("c", herramienta="Flow", prompt="p3", estado="generado", gancho="pergunta")
    assert s.marcar("a", "ok", movimiento=12.0)
    assert s.marcar("b", "defecto", nota="mao extra", movimiento=8.0)
    assert s.marcar("c", "ok", movimiento=20.0)

    assert s.informe() == [("pergunta", 1, 1, 0, 20.0), ("resultado", 2, 1, 1, 10.0)]
    assert s.defectos() == [("b", "mao extra", "p2")]


def test_marcar_toca_solo_el_ultimo_intento_del_nombre(tmp_path):
    s = IntentosStore(tmp_path / "g.db")
    s.registrar("a", herramienta="Flow", prompt="v1", estado="generado")
    s.registrar("a", herramienta="Flow", prompt="v2", estado="generado")
    s.marcar("a", "defecto", nota="x")

    assert s.defectos() == [("a", "x", "v2")]


def test_un_rechazo_cuenta_como_intento_sin_aprobar(tmp_path):
    s = IntentosStore(tmp_path / "g.db")
    s.registrar("a", herramienta="YouTube Create", prompt="p", estado="rechazado")

    assert s.informe() == [("sin gancho", 1, 0, 0, None)]


def test_marcar_un_nombre_desconocido_avisa(tmp_path):
    assert not IntentosStore(tmp_path / "g.db").marcar("nada", "ok")
