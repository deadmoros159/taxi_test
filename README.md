# Taxi Service - Микросервисная архитектура

Проект такси-сервиса с микросервисной архитектурой.

## 🚀 Быстрый старт

### Запуск всех сервисов

```bash
# Запуск всех сервисов
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка всех сервисов
docker-compose down

# Остановка с удалением volumes (БД)
docker-compose down -v
```

### Запуск миграций

```bash
# Запуск миграций auth-service
docker-compose --profile migrations up auth-migrations
```

## 📋 Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **auth-service** | 8000 | Аутентификация, авторизация, управление пользователями |
| **driver-service** | 8001 | Управление водителями и автомобилями |
| **order-service** | 8002 | Управление заказами |
| **api-gateway** | 8080 | API Gateway для всех сервисов |

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env` в `auth-service/`:

```env
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
FIREBASE_API_KEY=your_firebase_key
FIREBASE_PROJECT_ID=your_project_id
SMS_PROVIDER=firebase
```

### Базы данных

- **auth_db** - База данных для auth-service (PostgreSQL)
- **driver_db** - База данных для driver-service (PostgreSQL)
- **Redis** - Кэш и сессии для auth-service

## 📚 API Документация

После запуска сервисов:

- **auth-service**: http://localhost:8000/docs
- **driver-service**: http://localhost:8001/docs
- **order-service**: http://localhost:8002/docs

## 🏗️ Архитектура

Подробное описание архитектуры см. в [ARCHITECTURE.md](./ARCHITECTURE.md)

## 🔍 Проверка работоспособности

```bash
# Проверка health checks
curl http://localhost:8000/health  # auth-service
curl http://localhost:8001/health  # driver-service
curl http://localhost:8002/health  # order-service
```

## 🛠️ Разработка

### Запуск отдельного сервиса

```bash
# Только auth-service с зависимостями
docker-compose up postgres-auth redis auth-service

# Только driver-service
docker-compose up postgres-driver driver-service
```

### Логи конкретного сервиса

```bash
docker-compose logs -f auth-service
docker-compose logs -f driver-service
```

## 📝 Примечания

- Все сервисы используют общую сеть `taxi-network`
- Сервисы автоматически перезапускаются при падении (`restart: unless-stopped`)
- Health checks настроены для всех сервисов
- Volumes сохраняют данные БД между перезапусками

