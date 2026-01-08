#!/bin/bash

# Скрипт обновления проекта из GitHub
# Использование: ./update-from-github.sh [prod|dev]

set -e

ENV=${1:-prod}
PROJECT_DIR="/opt/taxi"

if [ "$ENV" != "prod" ] && [ "$ENV" != "dev" ]; then
    echo "❌ Ошибка: окружение должно быть 'prod' или 'dev'"
    exit 1
fi

echo "🔄 Обновление проекта из GitHub для окружения: $ENV"
echo ""

cd $PROJECT_DIR

# Проверяем, что это git репозиторий
if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "❌ Ошибка: директория не является git репозиторием"
    echo "Сначала запустите: ./setup-github.sh <repo-url>"
    exit 1
fi

# Сохраняем изменения в переменных окружения (если есть)
if [ -f "$PROJECT_DIR/deploy/env/.env.$ENV" ]; then
    echo "💾 Сохраняем переменные окружения..."
    cp "$PROJECT_DIR/deploy/env/.env.$ENV" /tmp/env_backup_$ENV
fi

# Получаем последние изменения
echo "📥 Получаем обновления из GitHub..."
git fetch origin
git pull origin main || git pull origin master

# Восстанавливаем переменные окружения
if [ -f "/tmp/env_backup_$ENV" ]; then
    echo "💾 Восстанавливаем переменные окружения..."
    cp /tmp/env_backup_$ENV "$PROJECT_DIR/deploy/env/.env.$ENV"
    rm /tmp/env_backup_$ENV
fi

echo "✅ Проект обновлен!"
echo ""
echo "Для применения изменений:"
echo "  cd /opt/taxi/deploy"
echo "  ./deploy.sh $ENV restart"

