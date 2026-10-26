from src.magalu import MAGALU_LOJA, link_afiliado_magalu

PRODUTO = "/cadeira-de-escritorio-giratoria/p/237764500/mo/cade/"
ESPERADO = f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/p/237764500/"


def test_convierte_link_de_magazineluiza_a_la_tienda():
    assert link_afiliado_magalu("https://www.magazineluiza.com.br" + PRODUTO) == ESPERADO


def test_link_real_del_moto_g17():
    # Probado a mano el 2026-10-26: abre el producto con la tienda Setupjusto arriba.
    url = (
        "https://www.magazineluiza.com.br/smartphone-motorola-moto-g17-4g-128gb-4gb-ram"
        "-8gb-ram-boost-camera-50mp-sony-lytia-600-tela-fhd-60hz-bateria-5200-mah/p/"
        "ek8d4d5f5a/te/mg17/?seller_id=lojamotorolaoficial&ads=patrocinado"
    )
    assert link_afiliado_magalu(url) == (
        f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/p/ek8d4d5f5a/"
    )


def test_acepta_version_movil_y_sin_www():
    for host in ("m.magazineluiza.com.br", "magazineluiza.com.br"):
        assert link_afiliado_magalu(f"https://{host}{PRODUTO}") == ESPERADO


def test_cambia_la_tienda_de_otro_divulgador_por_la_nuestra():
    url = "https://www.magazinevoce.com.br/magazineotrodivulgador" + PRODUTO
    assert link_afiliado_magalu(url) == ESPERADO


def test_none_si_no_es_un_producto_de_magalu():
    assert link_afiliado_magalu("https://www.magazineluiza.com.br/busca/cadeira/") is None
    assert link_afiliado_magalu("https://shopee.com.br/produto-i.1.2") is None
    assert link_afiliado_magalu("") is None
