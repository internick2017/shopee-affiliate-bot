from src.link_extractor import extract_shopee_links


def test_extracts_single_shortlink():
    text = "🛒 Compre aqui: https://s.shopee.com.br/6KxbHWtz5C"
    assert extract_shopee_links(text) == ["https://s.shopee.com.br/6KxbHWtz5C"]


def test_returns_empty_when_no_shopee_link():
    assert extract_shopee_links("Sem link aqui, só texto") == []


def test_extracts_multiple_links():
    text = "a https://s.shopee.com.br/AAA b https://s.shopee.com.br/BBB"
    assert extract_shopee_links(text) == [
        "https://s.shopee.com.br/AAA",
        "https://s.shopee.com.br/BBB",
    ]


def test_handles_empty_and_none():
    assert extract_shopee_links("") == []
    assert extract_shopee_links(None) == []
