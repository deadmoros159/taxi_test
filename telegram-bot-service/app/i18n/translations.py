"""Переводы для бота: русский и узбекский."""

TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать в Taxi Service!\n👋 Taxi Service ga xush kelibsiz!\n\nВыберите язык / Tilni tanlang:",
        "choose_lang": "Выберите язык:",
        "btn_russian": "🇷🇺 Русский",
        "btn_uzbek": "🇺🇿 O'zbek",
        "lang_set": "✅ Язык: Русский",
        "welcome_reg": "Для регистрации необходимо отправить ваш номер телефона.\nНажмите кнопку ниже:",
        "btn_send_contact": "📱 Отправить мой аккаунт",
        "wrong_contact": "❌ Пожалуйста, отправьте именно ваш контакт.\nИспользуйте кнопку 'Отправить мой аккаунт'.",
        "auth_processing": "⏳ Авторизация...",
        "auth_success": "✅ <b>Авторизация успешна!</b>\n\n{id_line}{phone_line}\nНажмите кнопку ниже, чтобы вернуться в приложение.",
        "auth_success_id": "👤 Ваш ID: {user_id}\n",
        "auth_success_phone": "📱 Номер: {phone}\n\n",
        "btn_back_to_app": "◀️ Вернуться в приложение",
        "already_registered": "✅ Вы уже зарегистрированы.\n\nНажмите кнопку, чтобы вернуться в приложение.",
        "auth_code_error": "❌ Ошибка при создании кода. Попробуйте позже.",
        "auth_error": "❌ Ошибка авторизации. Попробуйте позже или обратитесь в поддержку.",
        "auth_error_generic": "❌ Произошла ошибка при авторизации. Попробуйте позже.",
        # Order status notifications
        "order_status_pending": "📋 Заказ #{order_id}\nСтатус: Ожидает водителя",
        "order_status_accepted": "✅ Заказ #{order_id}\nСтатус: Водитель принял заказ",
        "order_status_driver_arrived": "🚗 Заказ #{order_id}\nСтатус: Водитель прибыл",
        "order_status_in_progress": "🛣 Заказ #{order_id}\nСтатус: В пути",
        "order_status_completed": "✅ Заказ #{order_id}\nСтатус: Завершён",
        "order_status_cancelled": "❌ Заказ #{order_id}\nСтатус: Отменён",
        "order_status_cancelled_by_driver": "❌ Заказ #{order_id}\nСтатус: Отменён водителем",
        "order_status_cancelled_by_passenger": "❌ Заказ #{order_id}\nСтатус: Отменён пассажиром",
    },
    "uz": {
        "welcome": "👋 Добро пожаловать в Taxi Service!\n👋 Taxi Service ga xush kelibsiz!\n\nВыберите язык / Tilni tanlang:",
        "choose_lang": "Tilni tanlang:",
        "btn_russian": "🇷🇺 Русский",
        "btn_uzbek": "🇺🇿 O'zbek",
        "lang_set": "✅ Til: O'zbek",
        "welcome_reg": "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring.\nQuyidagi tugmani bosing:",
        "btn_send_contact": "📱 Mening raqamimni yuborish",
        "wrong_contact": "❌ Iltimos, o'zingizning kontaktingizni yuboring.\n'Raqamimni yuborish' tugmasidan foydalaning.",
        "auth_processing": "⏳ Avtorizatsiya...",
        "auth_success": "✅ <b>Muvaffaqiyatli avtorizatsiya!</b>\n\n{id_line}{phone_line}\nIlovaga qaytish uchun quyidagi tugmani bosing.",
        "auth_success_id": "👤 Sizning ID: {user_id}\n",
        "auth_success_phone": "📱 Raqam: {phone}\n\n",
        "btn_back_to_app": "◀️ Ilovaga qaytish",
        "already_registered": "✅ Siz allaqachon ro'yxatdan o'tgansiz.\n\nIlovaga qaytish uchun tugmani bosing.",
        "auth_code_error": "❌ Kod yaratishda xatolik. Keyinroq qaytadan urinib ko'ring.",
        "auth_error": "❌ Avtorizatsiya xatosi. Keyinroq urinib ko'ring yoki qo'llab-quvvatlash bilan bog'laning.",
        "auth_error_generic": "❌ Avtorizatsiya paytida xatolik yuz berdi. Keyinroq urinib ko'ring.",
        # Order status notifications
        "order_status_pending": "📋 Buyurtma #{order_id}\nHolat: Haydovchi kutyapti",
        "order_status_accepted": "✅ Buyurtma #{order_id}\nHolat: Haydovchi qabul qildi",
        "order_status_driver_arrived": "🚗 Buyurtma #{order_id}\nHolat: Haydovchi yetib keldi",
        "order_status_in_progress": "🛣 Buyurtma #{order_id}\nHolat: Yo'lda",
        "order_status_completed": "✅ Buyurtma #{order_id}\nHolat: Yakunlandi",
        "order_status_cancelled": "❌ Buyurtma #{order_id}\nHolat: Bekor qilindi",
        "order_status_cancelled_by_driver": "❌ Buyurtma #{order_id}\nHolat: Haydovchi tomonidan bekor qilindi",
        "order_status_cancelled_by_passenger": "❌ Buyurtma #{order_id}\nHolat: Yo'lovchi tomonidan bekor qilindi",
    },
}

DEFAULT_LANG = "ru"


def get_text(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Получить перевод по ключу. kwargs подставляются в строку (format)."""
    texts = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    s = texts.get(key, TEXTS[DEFAULT_LANG].get(key, key))
    if kwargs:
        return s.format(**kwargs)
    return s
