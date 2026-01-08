#!/bin/bash

# Скрипт настройки GitHub репозитория для деплоя
# Использование: ./setup-github.sh <github-repo-url>

set -e

if [ -z "$1" ]; then
    echo "❌ Ошибка: укажите URL репозитория GitHub"
    echo "Использование: ./setup-github.sh git@github.com:username/repo.git"
    exit 1
fi

REPO_URL=$1
PROJECT_DIR="/opt/taxi"

echo "🔧 Настройка GitHub репозитория для деплоя..."
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Ошибка: скрипт должен запускаться от root"
    exit 1
fi

# Создаем директорию для проекта
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Проверяем, есть ли уже репозиторий
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "⚠️  Репозиторий уже существует, обновляем..."
    git pull origin main || git pull origin master
else
    echo "📥 Клонируем репозиторий..."
    git clone $REPO_URL .
fi

# Настраиваем Git (если нужно)
git config --global --add safe.directory $PROJECT_DIR || true

# Проверяем наличие необходимых директорий
if [ ! -d "$PROJECT_DIR/deploy" ]; then
    echo "❌ Ошибка: директория deploy не найдена в репозитории"
    exit 1
fi

echo "✅ Репозиторий настроен!"
echo ""
echo "Следующие шаги:"
echo "  1. Настройте SSL сертификаты: /opt/taxi/deploy/ssl/"
echo "  2. Настройте переменные окружения: /opt/taxi/deploy/env/.env.prod"
echo "  3. Запустите деплой: cd /opt/taxi/deploy && ./deploy.sh prod start"

