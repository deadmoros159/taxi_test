# Telegram Bot Service

Сервис Telegram бота для авторизации через Telegram и управления заказами такси.

## Функциональность

- 🔐 Авторизация через Telegram (без SMS кода)
- 📱 Получение контакта пользователя через кнопку
- 🎫 Выдача JWT токенов после авторизации
- 🔔 Уведомления (в разработке)
- 📋 Управление заказами через бот (в разработке)

## Как это работает

1. Пользователь отправляет `/start` боту в Telegram
2. Telegram отправляет обновление на webhook URL
3. Бот показывает кнопку "📱 Отправить мой аккаунт"
4. Пользователь нажимает кнопку и отправляет свой контакт
5. Бот получает номер телефона и отправляет запрос в `auth-service`
6. `auth-service` создает/находит пользователя и выдает JWT токены
7. Бот отправляет токены пользователю

## Webhook vs Polling

Бот использует **webhook** вместо polling:
- ✅ Более эффективно (Telegram отправляет обновления напрямую)
- ✅ Меньше нагрузка на сервер
- ✅ Лучше для production

**Важно:** Для работы webhook нужен публичный URL, доступный из интернета (HTTPS для production).

## Запуск

### Локально (для разработки)

```bash
cd telegram-bot-service

# Создать .env файл
cat > .env << EOF
TELEGRAM_BOT_TOKEN=8577887798:AAEMGcMot27E9iY7dEunLRxbkG5maA77s6Y
AUTH_SERVICE_URL=http://localhost:8000
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
EOF

# Установить зависимости
pip install -r requirements.txt

# Запустить бота
python app/main.py
```

### Через Docker Compose

```bash
# Из корня проекта
# Для локальной разработки (webhook будет на localhost)
docker-compose up -d telegram-bot-service

# Для production (нужен публичный URL)
WEBHOOK_HOST=https://yourdomain.com docker-compose up -d telegram-bot-service

# Просмотр логов
docker-compose logs -f telegram-bot-service
```

**Важно для production:**
- Webhook URL должен быть доступен из интернета (HTTPS обязателен)
- Убедитесь, что Nginx/прокси настроен для проксирования `/webhook` на порт 8004
- Пример webhook URL: `https://xhap.ru/telegram/webhook`

## Переменные окружения

| Переменная | Описание | Обязательно | По умолчанию |
|-----------|----------|-------------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота от @BotFather | Да | - |
| `AUTH_SERVICE_URL` | URL auth-service API | Нет | http://auth-service:8000 |
| `WEBHOOK_HOST` | Публичный URL для webhook (должен быть доступен из интернета) | Да | http://localhost:8004 |
| `WEBHOOK_PATH` | Путь для webhook endpoint | Нет | /webhook |
| `WEBHOOK_SECRET` | Секретный ключ для webhook (опционально) | Нет | - |
| `HOST` | Хост для сервера | Нет | 0.0.0.0 |
| `PORT` | Порт для сервера | Нет | 8004 |
| `ENVIRONMENT` | Окружение (development/production) | Нет | development |
| `DEBUG` | Режим отладки | Нет | true |
| `LOG_LEVEL` | Уровень логирования | Нет | INFO |

## API Endpoint

Бот использует endpoint в `auth-service`:

- `POST /api/v1/auth/telegram/authorize` - Авторизация через Telegram

## Структура проекта

```
telegram-bot-service/
├── app/
│   ├── core/
│   │   └── config.py          # Конфигурация
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── auth.py             # Обработчики команд и контактов
│   ├── services/
│   │   └── auth_client.py      # Клиент для auth-service API
│   └── main.py                 # Точка входа
├── Dockerfile
├── requirements.txt
└── README.md
```

## Разработка

Бот использует `aiogram 3.4` для работы с Telegram Bot API.

### Добавление новых команд

1. Создайте обработчик в `app/handlers/`
2. Зарегистрируйте router в `app/main.py`

Пример:
```python
from aiogram import Router
from aiogram.filters import Command

router = Router()

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Это команда помощи")
```

