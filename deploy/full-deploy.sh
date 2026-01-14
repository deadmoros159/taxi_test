#!/bin/bash

# Полный скрипт деплоя с нуля
# Использование: ./full-deploy.sh [prod|dev]

set -e

ENV=${1:-prod}

if [ "$ENV" != "prod" ] && [ "$ENV" != "dev" ]; then
    echo "❌ Ошибка: окружение должно быть 'prod' или 'dev'"
    exit 1
fi

echo "🚀 Начинаем полный деплой для окружения: $ENV"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Ошибка: скрипт должен запускаться от root"
    exit 1
fi

# Шаг 1: Установка зависимостей
echo "📦 Шаг 1: Установка зависимостей..."
if [ ! -f "install.sh" ]; then
    echo "❌ Ошибка: файл install.sh не найден"
    exit 1
fi
bash install.sh

# Шаг 2: Настройка Nginx
echo ""
echo "🌐 Шаг 2: Настройка Nginx..."
if [ ! -f "setup-nginx.sh" ]; then
    echo "❌ Ошибка: файл setup-nginx.sh не найден"
    exit 1
fi
bash setup-nginx.sh

# Шаг 3: Проверка переменных окружения
echo ""
echo "🔐 Шаг 3: Проверка переменных окружения..."
if [ ! -f "env/.env.${ENV}" ]; then
    echo "⚠️  Файл env/.env.${ENV} не найден"
    echo "Создайте его на основе env/.env.${ENV}.example"
    exit 1
fi
echo "✅ Файл env/.env.${ENV} найден"

# Шаг 4: Проверка SSL
echo ""
echo "🔒 Шаг 4: Проверка SSL сертификатов..."
if [ ! -f "/opt/taxi/ssl/xhap.ru.key" ] || [ ! -f "/opt/taxi/ssl/xhap.ru.crt" ]; then
    echo "⚠️  SSL сертификаты не найдены в /opt/taxi/ssl/"
    echo "Скопируйте xhap.ru.key и xhap.ru.crt в /opt/taxi/ssl/"
    exit 1
fi
echo "✅ SSL сертификаты найдены"

# Шаг 5: Деплой сервисов
echo ""
echo "🐳 Шаг 5: Деплой сервисов..."
./deploy.sh $ENV start

# Шаг 6: Запуск мониторинга (опционально)
echo ""
read -p "Запустить мониторинг? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📊 Запуск мониторинга..."
    cd monitoring
    docker-compose -f docker-compose.monitoring.yml up -d
    cd ..
    echo "✅ Мониторинг запущен"
fi

echo ""
echo "✅ Деплой завершен!"
echo ""
echo "Доступные эндпоинты:"
if [ "$ENV" == "prod" ]; then
    echo "  - https://xhap.ru/auth"
    echo "  - https://xhap.ru/driver"
    echo "  - https://xhap.ru/order"
    echo "  - https://xhap.ru/admin"
    echo "  - https://xhap.ru/grafana (мониторинг)"
    echo "  - https://xhap.ru/prometheus (метрики)"
else
    echo "  - https://dev.xhap.ru/auth"
    echo "  - https://dev.xhap.ru/driver"
    echo "  - https://dev.xhap.ru/order"
    echo "  - https://dev.xhap.ru/admin"
fi
echo ""
echo "Проверка статуса:"
docker ps --filter "name=taxi-${ENV}"


