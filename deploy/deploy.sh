#!/bin/bash

# Скрипт деплоя микросервисов
# Использование: ./deploy.sh [prod|dev] [start|stop|restart|rebuild|logs] [service]
# rebuild — пересборка образов (для применения изменений кода)

set -e

ENV=${1:-prod}
ACTION=${2:-start}
SERVICE=${3:-}

if [ "$ENV" != "prod" ] && [ "$ENV" != "dev" ]; then
    echo "❌ Ошибка: окружение должно быть 'prod' или 'dev'"
    exit 1
fi

if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ] && [ "$ACTION" != "restart" ] && [ "$ACTION" != "rebuild" ] && [ "$ACTION" != "logs" ]; then
    echo "❌ Ошибка: действие должно быть 'start', 'stop', 'restart', 'rebuild' или 'logs'"
    exit 1
fi

COMPOSE_FILE="docker-compose.${ENV}.yml"
PROJECT_NAME="taxi-${ENV}"

# Проверяем наличие файла
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Ошибка: файл $COMPOSE_FILE не найден"
    exit 1
fi

# Загружаем переменные окружения
if [ -f "env/.env.${ENV}" ]; then
    export $(cat env/.env.${ENV} | grep -v '^#' | xargs)
    echo "✅ Загружены переменные окружения из env/.env.${ENV}"
else
    echo "⚠️  Файл env/.env.${ENV} не найден, используем переменные из окружения"
fi

cd "$(dirname "$0")"

case $ACTION in
    start)
        echo "🚀 Запуск сервисов для окружения: $ENV"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build
        echo "✅ Сервисы запущены"
        echo ""
        echo "Проверка статуса:"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
        ;;
    stop)
        echo "🛑 Остановка сервисов для окружения: $ENV"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
        echo "✅ Сервисы остановлены"
        ;;
    restart)
        echo "🔄 Перезапуск сервисов для окружения: $ENV"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart
        echo "✅ Сервисы перезапущены"
        ;;
    rebuild)
        echo "🔨 Пересборка и перезапуск для окружения: $ENV"
        if [ -n "$SERVICE" ]; then
            echo "   Сервис: $SERVICE"
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build $SERVICE
        else
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build
        fi
        echo "✅ Пересборка завершена"
        echo ""
        echo "Проверка статуса:"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
        ;;
    logs)
        echo "📋 Логи сервисов для окружения: $ENV"
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f
        ;;
    *)
        echo "❌ Неизвестное действие: $ACTION"
        exit 1
        ;;
esac


