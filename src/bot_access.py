"""Control de acceso del bot generador de posts: whitelist de user_id de Telegram."""


def parse_allowed_users(raw: str | None) -> set[int]:
    """Parsea `BOT_ALLOWED_USERS` ("123,456") a un set de ints. Tokens no
    numéricos se ignoran en vez de romper el arranque del bot."""
    if not raw:
        return set()
    result = set()
    for token in raw.split(","):
        token = token.strip()
        if token.lstrip("-").isdigit():
            result.add(int(token))
    return result
