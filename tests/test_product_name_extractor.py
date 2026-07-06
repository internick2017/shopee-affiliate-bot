from src.product_name_extractor import extract_product_names


def test_single_product_with_hype():
    text = (
        "O GLOSS FAMOSINHO DO TIKTOK\n\n"
        "Gloss Fran By Franciny Ehlke Liphoney\n\n"
        "De R$ 69 por R$ 23\n\n"
        "Vendido por Loja Oficial no ML\n"
        "https://meli.la/1ShxGBP\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == ["Gloss Fran By Franciny Ehlke Liphoney"]


def test_fire_prefixed_product_amazon():
    text = (
        "🔥 Placa de Video Nv RTX5060TI 8GB GDDR7 128BITS Ventus 2x OC Plus MSI 912-V536-023\n\n"
        "💵 R$ 2391\n"
        "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=crowmantech-20\n\n"
        "anúncio\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == [
        "Placa de Video Nv RTX5060TI 8GB GDDR7 128BITS Ventus 2x OC Plus MSI 912-V536-023"
    ]


def test_multiple_products():
    text = (
        "Kit 12 Cuecas Boxer Polo Wear Masculino Microfibra Liso\n"
        "🔥 R$ 82,06 via pix\n"
        "⚠️ Cupom: MODAPROMO\n"
        "🛍 https://meli.la/1Kh6Zjx\n\n"
        "Tenis Mizuno Jet 8 - Masculino (+ cores)\n"
        "🔥 R$ 217,26 no PIX \n"
        "🎟 Cupom: MODAPROMO\n"
        "🛒 https://meli.la/2HVVHMG\n\n"
        "Armani Beauty Perfume Feminino My Way Eau de Parfum, Refilável 30ml\n"
        "🔥 R$ 259,19 via pix\n"
        "⚠️ Cupom: PLACARZAO\n"
        "🛍 https://meli.la/1FUkaeF\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == [
        "Kit 12 Cuecas Boxer Polo Wear Masculino Microfibra Liso",
        "Tenis Mizuno Jet 8 - Masculino (+ cores)",
        "Armani Beauty Perfume Feminino My Way Eau de Parfum, Refilável 30ml",
    ]


def test_coupon_only_message_returns_empty():
    text = (
        "NOVO CUPOM AMAZON\n\n"
        "10% OFF em compras acima de R$ 250\n"
        "Limite de R$ 50\n\n"
        "Use o Cupom: PRIMEDAY2026 🎟️\n"
        "https://www.amazon.com.br/?linkCode=sl2&tag=crowmantech-20\n\n"
        "- exclusivo para membros prime\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == []


def test_two_line_hype_with_seller():
    text = (
        "PREÇÃO NESSE ÁRABE\n"
        "lembra demais o le male elixir\n\n"
        "Perfume Lattafa The Kingdom EDP 100ml\n\n"
        "De R$ 408 por R$ 167 no Pix\n"
        "Use o Cupom: *CARRINHOCHEIOML* ou *SALVAESSA* 🎟️ + Selecione *Pix*\n\n"
        "Vendido por Loja Oficial no ML\n"
        "https://meli.la/2NBCphd\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == ["Perfume Lattafa The Kingdom EDP 100ml"]


def test_price_a_vista_without_rs_prefix():
    text = (
        "ORGANIZA ESSAS ROUPA EMBOLADA AI\n\n"
        "Kit 50 un. Cabide Adulto Reforçado\n\n"
        "28,99 à vista\n"
        "https://meli.la/2tHwf7w\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == ["Kit 50 un. Cabide Adulto Reforçado"]


def test_amazon_prime_with_bullets():
    text = (
        "ESSE É NA ESCALA 7 X 0\n"
        "oferta exclusiva prime\n\n"
        "Robô Aspirador WAP W90\n"
        "- resgate o cupom de 10% no anuncio\n\n"
        "224,61 em até 6x\n"
        "https://www.amazon.com.br/dp/B0B9PSBNYL?tag=crowmantech-20\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert extract_product_names(text) == ["Robô Aspirador WAP W90"]


def test_empty_and_none():
    assert extract_product_names("") == []
    assert extract_product_names(None) == []


def test_iachados_de_por_product_name():
    text = (
        "COM ESSA MAIONESE, ATÉ O PÃO FICA CHIQUE DEMAIS! 😎\n\n"
        "🍔 Heinz Maionese Alho Tostado Com Ervas 215g\n\n"
        "🔥 DE 13,59 | POR 9,16\n"
        "🎟 CUPOM: MERCADO\n\n"
        "🔗 https://www.amazon.com.br/dp/B0B25NN5HL?th=1&psc=1&tag=iachadospromo-20\n\n"
        "🔹 Oferta exclusiva membros Amazon Prime.\n\n"
        "🛍️ IAchados"
    )
    assert extract_product_names(text) == ["Heinz Maionese Alho Tostado Com Ervas 215g"]


def test_iachados_primeday_coupon_returns_empty():
    text = (
        "ESSE DESCONTO É MELHOR QUE ACHADO EM GARAGEM!\n\n"
        "➡️ 10% OFF a partir de R$300, limitado a R$100 OFF\n"
        "🎟 cupom: PRIMEIRO\n\n"
        "🔗 https://www.amazon.com.br/primeday?tag=iachadospromo-20\n\n"
        "🛍️ IAchados"
    )
    assert extract_product_names(text) == []
