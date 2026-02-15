from aiogram import Router, F, Bot
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, Contact, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
import logging
import urllib.parse
import httpx
from app.services.auth_client import AuthClient
from app.services.media_client import MediaClient

logger = logging.getLogger(__name__)

router = Router()


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


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user = message.from_user
    telegram_user_id = user.id

    # Проверяем, есть ли пользователь уже в БД по telegram_user_id
    auth_client = AuthClient()
    try:
        check = await auth_client.telegram_user_exists(telegram_user_id)
        if check and check.get("exists") is True:
            # Пользователь уже зарегистрирован — контакт не просим
            await message.answer(
                "✅ Вы уже зарегистрированы.\n\n"
                "Авторизация доступна без отправки аккаунта.\n"
                "Используйте клиентское приложение для получения токенов через API.",
                reply_markup=None
            )
            return
    except Exception as e:
        logger.error(f"Error in cmd_start check: {e}", exc_info=True)
    finally:
        await auth_client.close()

    # Если пользователя нет — просим отправить аккаунт/контакт
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
            user_id = result.get("user_id")
            
            # Формируем deep link для мобильного приложения
            # Формат: taxiapp://auth?telegram_id=...&phone=...&name=...&photo_id=...&username=...
            # Все параметры обязательны для корректной работы deep link
            deep_link_params = {
                "telegram_id": str(telegram_user_id),
                "phone": urllib.parse.quote(phone_number),
                "name": urllib.parse.quote(full_name)
            }
            
            # Добавляем опциональные параметры
            if telegram_username:
                deep_link_params["username"] = urllib.parse.quote(telegram_username)
            
            if photo_id:
                deep_link_params["photo_id"] = str(photo_id)
            
            # Формируем deep link
            deep_link = "taxiapp://auth?" + "&".join([f"{k}={v}" for k, v in deep_link_params.items()])
            
            # Отправляем сообщение с deep link
            # Пользователь может нажать на ссылку, и приложение откроется автоматически
            response_text = (
                "✅ <b>Авторизация успешна!</b>\n\n"
                f"👤 Ваш ID: {user_id}\n"
                f"📱 Номер: {phone_number}\n\n"
                "💡 <b>Нажмите на ссылку ниже, чтобы открыть приложение:</b>\n\n"
                f"🔗 <a href=\"{deep_link}\">{deep_link}</a>\n\n"
                "<i>Если ссылка не открывает приложение, откройте приложение вручную и войдите по номеру телефона.</i>"
            )

            await message.answer(
                response_text,
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

