import logging
import time
import urllib.parse

from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, Contact, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, CommandObject

from app.services.auth_client import AuthClient
from app.services.media_client import MediaClient

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


def _build_redirect_url(code: str, state: str | None = None) -> str:
    """https://... — для InlineKeyboardButton (Telegram не поддерживает taxiapp://)."""
    from app.core.config import settings
    base = str(settings.APP_REDIRECT_BASE_URL).rstrip("/")
    params = {"code": code}
    if state:
        params["state"] = state
    return f"{base}/app/auth?" + urllib.parse.urlencode(params)


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отправки контакта"""
    contact_button = KeyboardButton(
        text="📱 Отправить мой аккаунт",
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
    Флоу: приложение открывает t.me/bot?start=STATE → бот возвращает taxiapp://auth?state=STATE&token=...
    """
    user = message.from_user
    telegram_user_id = user.id

    # Сохраняем state из payload (t.me/bot?start=STATE)
    state = (command.args or "").strip() if command and command.args else None
    if state:
        _set_state(telegram_user_id, state)

    auth_client = AuthClient()
    try:
        check = await auth_client.telegram_user_exists(telegram_user_id)
        if check and check.get("exists") is True:
            # Пользователь уже зарегистрирован — создаём код, кнопка ведёт на https (редирект на taxiapp://)
            code = await auth_client.create_telegram_auth_code(telegram_user_id=telegram_user_id)
            if code:
                btn_url = _build_redirect_url(code, state)
                _clear_state(telegram_user_id)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Вернуться в приложение", url=btn_url)]
                ])
                await message.answer(
                    "✅ Вы уже зарегистрированы.\n\nНажмите кнопку, чтобы вернуться в приложение.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка при создании кода. Попробуйте позже.")
            return
    except Exception as e:
        logger.error(f"Error in cmd_start check: {e}", exc_info=True)
    finally:
        await auth_client.close()

    # Новый пользователь — просим отправить контакт (state уже сохранён выше)
    await message.answer(
        "👋 Добро пожаловать в Taxi Service!\n\n"
        "Для регистрации необходимо отправить ваш номер телефона.\n"
        "Нажмите кнопку ниже для отправки контакта:",
        reply_markup=get_contact_keyboard()
    )


@router.message(F.contact)
async def handle_contact(message: Message):
    """Обработка получения контакта от пользователя"""
    contact: Contact = message.contact
    user = message.from_user

    # Проверяем, что контакт принадлежит отправителю
    if contact.user_id != user.id:
        await message.answer(
            "❌ Пожалуйста, отправьте именно ваш контакт.\n"
            "Используйте кнопку 'Отправить мой аккаунт'."
        )
        return

    # Форматируем номер телефона (добавляем + если отсутствует)
    phone_number = contact.phone_number
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "User"
    telegram_user_id = user.id
    telegram_username = user.username

    await message.answer("⏳ Авторизация...")

    # Получаем фото профиля из Telegram
    # Используем глобальный объект bot из main.py
    from app.main import bot as global_bot
    photo_id = None
    try:
        if global_bot:
            photos = await global_bot.get_user_profile_photos(telegram_user_id, limit=1)
            if photos.total_count > 0:
                # Получаем самое большое фото
                photo = photos.photos[0][-1]  # Последний элемент - самое большое фото
                file = await global_bot.get_file(photo.file_id)
                
                # Скачиваем фото (download_file возвращает bytes напрямую)
                photo_bytes = await global_bot.download_file(file.file_path)
                
                # Загружаем в media-service
                media_client = MediaClient()
                try:
                    upload_result = await media_client.upload_file(
                        file_data=photo_bytes,
                        filename=f"profile_{telegram_user_id}.jpg",
                        mime_type="image/jpeg",
                        tag="PROFILE_PHOTO"
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
        # Продолжаем без фото

    # Авторизация через auth-service
    auth_client = AuthClient()
    try:
        result = await auth_client.authorize_via_telegram(
            phone_number=phone_number,
            full_name=full_name,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            photo_id=photo_id,
            email=None  # Email недоступен через Bot API
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
                await message.answer("❌ Ошибка при создании кода. Попробуйте позже.")
                return

            btn_url = _build_redirect_url(code, state)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Вернуться в приложение", url=btn_url)]
            ])

            id_line = f"👤 Ваш ID: {user_id}\n" if user_id else ""
            response_text = (
                "✅ <b>Авторизация успешна!</b>\n\n"
                f"{id_line}"
                f"📱 Номер: {phone_number}\n\n"
                "Нажмите кнопку ниже, чтобы вернуться в приложение."
            )

            await message.answer(
                response_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка авторизации. Попробуйте позже или обратитесь в поддержку."
            )

    except Exception as e:
        logger.error(f"Error in handle_contact: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при авторизации. Попробуйте позже."
        )
    finally:
        await auth_client.close()

