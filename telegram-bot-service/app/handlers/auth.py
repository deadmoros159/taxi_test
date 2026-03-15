import logging
import time
import urllib.parse

from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, Contact, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart, CommandObject

from app.services.auth_client import AuthClient
from app.services.media_client import MediaClient
from app.i18n.translations import get_text, TEXTS, DEFAULT_LANG
from app.lang_store import get_user_lang as _get_lang_stored, set_user_lang as _set_lang_stored

logger = logging.getLogger(__name__)

router = Router()

# Кэш state по telegram_user_id (TTL 15 мин). Приложение передаёт state в t.me/bot?start=STATE
_state_cache: dict[int, tuple[str, float]] = {}
_STATE_TTL = 15 * 60


def _get_state(telegram_user_id: int) -> str | None:
    now = time.time()
    if telegram_user_id in _state_cache:
        state, ts = _state_cache[telegram_user_id]
        if now - ts < _STATE_TTL:
            return state
        del _state_cache[telegram_user_id]
    return None


def _set_state(telegram_user_id: int, state: str) -> None:
    _state_cache[telegram_user_id] = (state, time.time())


def _clear_state(telegram_user_id: int) -> None:
    _state_cache.pop(telegram_user_id, None)


def _get_lang(telegram_user_id: int) -> str:
    return _get_lang_stored(telegram_user_id)


def _set_lang(telegram_user_id: int, lang: str) -> None:
    _set_lang_stored(telegram_user_id, lang)


def _get_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=TEXTS["ru"]["btn_russian"], callback_data="lang:ru"),
            InlineKeyboardButton(text=TEXTS["uz"]["btn_uzbek"], callback_data="lang:uz"),
        ]
    ])


def _build_redirect_url(code: str, state: str | None = None) -> str:
    from app.core.config import settings
    base = str(settings.APP_REDIRECT_BASE_URL).rstrip("/")
    params = {"code": code}
    if state:
        params["state"] = state
    return f"{base}/app/auth?" + urllib.parse.urlencode(params)


def get_contact_keyboard(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    contact_button = KeyboardButton(
        text=get_text("btn_send_contact", lang),
        request_contact=True
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[contact_button]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject | None = None):
    """
    Приветствие на обоих языках + выбор языка (🇷🇺 Русский / 🇺🇿 O'zbek).
    После выбора — регистрация или возврат в приложение.
    """
    user = message.from_user
    telegram_user_id = user.id
    lang = _get_lang(telegram_user_id)

    state = (command.args or "").strip() if command and command.args else None
    if state:
        _set_state(telegram_user_id, state)

    auth_client = AuthClient()
    try:
        check = await auth_client.telegram_user_exists(telegram_user_id)
        if check and check.get("exists") is True:
            code = await auth_client.create_telegram_auth_code(telegram_user_id=telegram_user_id)
            if code:
                btn_url = _build_redirect_url(code, state)
                _clear_state(telegram_user_id)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("btn_back_to_app", lang), url=btn_url)]
                ])
                await message.answer(
                    get_text("already_registered", lang),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await message.answer(get_text("auth_code_error", lang))
            return
    except Exception as e:
        logger.error(f"Error in cmd_start check: {e}", exc_info=True)
    finally:
        await auth_client.close()

    # Приветствие на двух языках + кнопки выбора языка
    await message.answer(
        get_text("welcome", "ru"),  # одинаковое билингвальное приветствие
        reply_markup=_get_lang_keyboard()
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery):
    """Обработка выбора языка."""
    lang = callback.data.replace("lang:", "")
    if lang not in ("ru", "uz"):
        await callback.answer()
        return

    telegram_user_id = callback.from_user.id
    _set_lang(telegram_user_id, lang)

    await callback.message.edit_text(get_text("lang_set", lang), reply_markup=None)
    await callback.message.answer(
        get_text("welcome_reg", lang),
        reply_markup=get_contact_keyboard(lang)
    )
    await callback.answer()


@router.message(F.contact)
async def handle_contact(message: Message):
    contact: Contact = message.contact
    user = message.from_user
    telegram_user_id = user.id
    lang = _get_lang(telegram_user_id)

    if contact.user_id != user.id:
        await message.answer(get_text("wrong_contact", lang))
        return

    phone_number = contact.phone_number
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "User"
    telegram_username = user.username

    await message.answer(get_text("auth_processing", lang))

    from app.main import bot as global_bot
    photo_id = None
    try:
        if global_bot:
            photos = await global_bot.get_user_profile_photos(telegram_user_id, limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]
                file = await global_bot.get_file(photo.file_id)
                
                photo_bytes = await global_bot.download_file(file.file_path)
                media_client = MediaClient()
                try:
                    upload_result = await media_client.upload_file(
                        file_data=photo_bytes,
                        filename=f"profile_{telegram_user_id}.jpg",
                        mime_type="image/jpeg",
                        tag="profile_photo"
                    )
                    if upload_result:
                        photo_id = upload_result.get("media_id")
                        logger.info(f"Profile photo uploaded: photo_id={photo_id}")
                except Exception as e:
                    logger.error(f"Error uploading photo to media-service: {e}", exc_info=True)
                finally:
                    await media_client.close()
    except Exception as e:
        logger.warning(f"Could not get profile photo: {e}", exc_info=True)

    auth_client = AuthClient()
    try:
        result = await auth_client.authorize_via_telegram(
            phone_number=phone_number,
            full_name=full_name,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            photo_id=photo_id,
            email=None
        )

        if result:
            access_token = result.get("access_token")
            refresh_token = result.get("refresh_token")
            user_id = result.get("user_id")
            state = _get_state(telegram_user_id)
            _clear_state(telegram_user_id)

            code = await auth_client.create_telegram_auth_code(
                access_token=access_token,
                refresh_token=refresh_token,
            )
            if not code:
                await message.answer(get_text("auth_code_error", lang))
                return

            btn_url = _build_redirect_url(code, state)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_back_to_app", lang), url=btn_url)]
            ])

            id_line = get_text("auth_success_id", lang, user_id=user_id) if user_id else ""
            phone_line = get_text("auth_success_phone", lang, phone=phone_number)
            response_text = get_text("auth_success", lang, id_line=id_line, phone_line=phone_line)

            await message.answer(
                response_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(get_text("auth_error", lang))

    except Exception as e:
        logger.error(f"Error in handle_contact: {e}", exc_info=True)
        await message.answer(get_text("auth_error_generic", lang))
    finally:
        await auth_client.close()

