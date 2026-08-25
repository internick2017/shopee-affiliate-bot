from src.bot_access import parse_allowed_users


def test_parse_allowed_users_lista_simple():
    assert parse_allowed_users("123,456") == {123, 456}


def test_parse_allowed_users_con_espacios():
    assert parse_allowed_users(" 123 , 456 ") == {123, 456}


def test_parse_allowed_users_vacio():
    assert parse_allowed_users("") == set()
    assert parse_allowed_users(None) == set()


def test_parse_allowed_users_ignora_tokens_no_numericos():
    assert parse_allowed_users("123,abc,456") == {123, 456}
