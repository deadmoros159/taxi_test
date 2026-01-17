from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, Contact
from aiogram.filters import Command
import logging
from app.services.auth_client import AuthClient

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
    await message.answer(
        "👋 Добро пожаловать в Taxi Service!\n\n"
        "Для авторизации необходимо отправить ваш номер телефона.\n"
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

    # Авторизация через auth-service
    auth_client = AuthClient()
    try:
        result = await auth_client.authorize_via_telegram(
            phone_number=phone_number,
            full_name=full_name,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username
        )

        if result:
            user_id = result.get("user_id")
            
            # Отправляем только подтверждение, токены не отправляем в чат
            response_text = (
                "✅ Авторизация успешна!\n\n"
                f"👤 Ваш ID: {user_id}\n"
                f"📱 Номер: {phone_number}\n\n"
                "💡 Токены были отправлены клиентскому приложению.\n"
                "📝 Используйте API endpoint для получения токенов."
            )

            await message.answer(
                response_text,
                parse_mode="HTML",
                reply_markup=None  # Убираем клавиатуру после авторизации
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

