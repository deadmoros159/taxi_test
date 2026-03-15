"""Хранилище языка пользователя (in-memory). Для production стоит перенести в Redis/DB."""

_user_lang: dict[int, str] = {}
DEFAULT_LANG = "ru"


def get_user_lang(telegram_user_id: int) -> str:
    return _user_lang.get(telegram_user_id, DEFAULT_LANG)


def set_user_lang(telegram_user_id: int, lang: str) -> None:
    if lang in ("ru", "uz"):
        _user_lang[telegram_user_id] = lang
