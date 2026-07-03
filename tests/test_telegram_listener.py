from src.telegram_listener import should_process


def test_empty_allowed_chats_processes_everything():
    assert should_process(123, "Cualquier Grupo", ()) is True


def test_matches_by_chat_id():
    assert should_process(123, "Grupo", (123,)) is True
    assert should_process(999, "Grupo", (123,)) is False


def test_matches_by_title_substring_case_insensitive():
    assert should_process(1, "Ofertas Shopee BR", ("ofertas",)) is True
    assert should_process(1, "Outro Grupo", ("ofertas",)) is False
