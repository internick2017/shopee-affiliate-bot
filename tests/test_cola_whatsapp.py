"""La parte de la cola de WhatsApp que decide, sin celular ni API."""

import datetime as dt
import random
from decimal import Decimal

from src.cola_whatsapp import (
    ColaStore,
    Envio,
    a_enviar,
    armar_cola,
    corrida,
    en_uso,
    plan_del_dia,
    texto_del_post,
)
from src.post_builder import HookBank
from src.product_ideas import Idea

MIERCOLES = dt.date(2026, 10, 28)
DOMINGO = dt.date(2026, 11, 1)


def idea(item_id, titulo, descuento=0, precio="29.90", categorias=(100636, 1, 2)):
    return Idea(item_id=item_id, titulo=titulo, precio=Decimal(precio), precio_min=None,
                precio_max=None, ventas=100, comision_pct=Decimal("8"), rating=Decimal("4.8"),
                descuento_pct=descuento, link=f"https://s.shopee.com.br/{item_id}",
                imagen_url=None, puntaje=1.0, categorias=categorias)


def buscador(pozos):
    """Cada busqueda devuelve su pozo menos lo excluido, como buscar_ideas."""
    return lambda b, excluir: [i for i in pozos.get(b, []) if i.item_id not in excluir]


def test_plan_lunes_a_sabado_dos_por_hora_ochenta_por_ciento_hogar():
    plan = plan_del_dia(MIERCOLES)
    assert [h for h, _ in plan][:3] == ["08:00", "08:30", "09:00"]
    assert plan[-1][0] == "21:30"
    assert len(plan) == 28
    rubro = [r for _, r in plan if r not in ("hogar", "ml")]
    assert len(rubro) == 6
    assert sum(r == "ml" for _, r in plan) == 3  # 10 % Mercado Livre
    assert set(rubro) <= {"celular", "audio", "informatica"}  # miercoles: electronicos


def test_el_rubro_del_dia_queda_repartido_no_amontonado():
    plan = plan_del_dia(MIERCOLES)
    posiciones = [i for i, (_, r) in enumerate(plan) if r != "hogar"]
    assert posiciones[0] < 5 and posiciones[-1] > 22


def test_domingo_no_hay_cola():
    assert plan_del_dia(DOMINGO) == []


def test_no_repite_producto_ni_tipo_de_producto_ni_lo_excluido():
    hogar = [idea(1, "Organizador de gaveta"), idea(2, "Organizador multiuso"),
             idea(3, "Pote hermetico"), idea(4, "Tapete banheiro")]
    pozos = {b: hogar for b in ("casa", "organizador cozinha", "utensilios cozinha", "limpeza",
                                "banheiro", "decoracao casa", "lavanderia", "potes",
                                "cama mesa banho", "organizador")}
    cola = armar_cola(MIERCOLES, buscador(pozos), HookBank(["OI"]), excluir={4})
    ids = [e.item_id for e in cola]
    assert len(ids) == len(set(ids))
    assert 4 not in ids
    assert not {1, 2} <= set(ids)  # dos "organizador" el mismo dia no
    assert all(e.rubro == "hogar" for e in cola)  # el pozo de electronicos estaba vacio: huecos


def test_texto_deriva_el_de_y_usa_el_template_de_lanny():
    t = texto_del_post(idea(9, "Kit potes", descuento=50, precio="20.00"), "CORRE")
    assert t.startswith("CORRE\n\n🛍️ Kit potes")
    assert "❌ De: R$ 40,00" in t and "✅ Por: R$ 20,00" in t
    assert "https://s.shopee.com.br/9" in t
    assert t.endswith("Promoção sujeita a alteração a qualquer momento.")


def test_manda_el_ultimo_vencido_y_da_por_vencidos_los_anteriores():
    cola = [Envio("2026-10-28", h, "hogar", i, "t", "x") for i, h in enumerate(["08:00", "08:30", "09:00"])]
    toca, viejos = a_enviar(cola, dt.datetime(2026, 10, 28, 8, 45))
    assert toca.hora == "08:30"
    assert [e.hora for e in viejos] == ["08:00"]
    assert a_enviar(cola, dt.datetime(2026, 10, 28, 7, 59)) == (None, [])


def test_store_guarda_una_vez_y_recuerda_lo_reciente(tmp_path):
    store = ColaStore(tmp_path / "c.db")
    e = Envio("2026-10-27", "08:00", "hogar", 7, "t", "x")
    store.guardar([e])
    store.guardar([Envio("2026-10-27", "08:00", "hogar", 8, "t", "y")])  # misma hora: se ignora
    assert [x.item_id for x in store.del_dia(dt.date(2026, 10, 27))] == [7]
    store.marcar(e, "enviado")
    assert store.del_dia(dt.date(2026, 10, 27))[0].estado == "enviado"
    assert store.de_la_semana(MIERCOLES) == {7}  # lunes 26 a miercoles 28: misma semana
    assert store.de_la_semana(dt.date(2026, 11, 2)) == set()  # el lunes siguiente vuelve


def test_hogar_solo_de_casa_e_cozinha_y_nada_caro():
    pozo = [idea(1, "Creatina pote 300g", categorias=(100001, 5, 6)),
            idea(2, "Tablet 10 polegadas", precio="399.00"),
            idea(3, "Pote hermetico vidro")]
    pozos = {b: pozo for b in ("casa", "organizador cozinha", "utensilios cozinha", "limpeza",
                               "banheiro", "decoracao casa", "lavanderia", "potes",
                               "cama mesa banho", "organizador")}
    cola = armar_cola(MIERCOLES, buscador(pozos), HookBank(["OI"]), excluir=set())
    assert [e.item_id for e in cola] == [3]


def test_la_hora_se_corre_al_azar_sin_juntar_dos_posts():
    azar = random.Random(1)
    horas = [corrida(h, azar) for h, _ in plan_del_dia(MIERCOLES)]
    minutos = [int(h[:2]) * 60 + int(h[3:]) for h in horas]
    assert all(b - a >= 15 for a, b in zip(minutos, minutos[1:], strict=False))
    assert any(m % 30 for m in minutos)  # no todas en punto ni y media
    assert horas[0] >= "08:00" and horas[-1] <= "21:45"


def test_en_uso_si_lo_tocaron_hace_menos_de_tres_minutos():
    assert en_uso("  lastUserActivityTime=997410661 (138109 ms ago)")  # medido 2026-10-28
    assert not en_uso("lastUserActivityTime=997410661 (180000 ms ago)")
    assert not en_uso("sin el dato")


POST_ML = "\n\n".join([
    "CORRE", "🛍️ Jogo de Toalhas 4 Pecas", "✅ Por: R$ 49,90",
    "🛒 Compre aqui: https://www.mercadolivre.com.br/p/MLB123?matt_word=x",
])


def test_candidato_ml_fresco_de_hogar_y_no_repetido_en_la_semana(tmp_path):
    store = ColaStore(tmp_path / "c.db")
    ahora = dt.datetime(2026, 10, 28, 15, 0)
    store.agregar_ml(POST_ML, ahora=ahora.timestamp() - 3600)
    store.agregar_ml(POST_ML.replace("Jogo de Toalhas", "Fone Bluetooth").replace("MLB123", "MLB9"),
                     ahora=ahora.timestamp() - 60)
    store.agregar_ml(POST_ML.replace("MLB123", "MLB7"), ahora=ahora.timestamp() - 13 * 3600)
    item_id, titulo, texto = store.candidato_ml(ahora)
    assert (item_id, titulo) == ("MLB123", "Jogo de Toalhas 4 Pecas")  # el fone no es hogar; MLB7 viejo
    store.marcar_ml_enviado("MLB123")
    assert store.candidato_ml(ahora) is None


def test_ml_mandado_la_semana_pasada_vuelve(tmp_path):
    store = ColaStore(tmp_path / "c.db")
    lunes = dt.datetime(2026, 11, 2, 9, 0)
    store.agregar_ml(POST_ML, ahora=lunes.timestamp() - 100)
    store._db.execute("UPDATE ml_candidatos SET enviado_ts = ?", (lunes.timestamp() - 3 * 86400,))
    assert store.candidato_ml(lunes)[0] == "MLB123"
