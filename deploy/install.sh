#!/bin/bash

# Скрипт установки всех зависимостей для деплоя
# Запускать от root: sudo bash install.sh

set -e

echo "🚀 Начинаем установку зависимостей..."

# Обновление системы
echo "📦 Обновление системы..."
apt-get update
apt-get upgrade -y

# Установка базовых пакетов
echo "📦 Установка базовых пакетов..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    net-tools \
    ufw \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

# Установка Docker
echo "🐳 Установка Docker..."
if ! command -v docker &> /dev/null; then
    # Удаляем старые версии
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Добавляем официальный GPG ключ Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Добавляем репозиторий Docker
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Устанавливаем Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    echo "✅ Docker установлен"
else
    echo "✅ Docker уже установлен"
fi

# Установка Docker Compose (standalone)
echo "🐳 Установка Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose установлен"
else
    echo "✅ Docker Compose уже установлен"
fi

# Установка Nginx
echo "🌐 Установка Nginx..."
if ! command -v nginx &> /dev/null; then
    apt-get install -y nginx
    systemctl enable nginx
    echo "✅ Nginx установлен"
else
    echo "✅ Nginx уже установлен"
fi

# Настройка firewall
echo "🔥 Настройка firewall..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
echo "✅ Firewall настроен"

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p /opt/taxi/{prod,dev,logs,ssl,monitoring}
mkdir -p /opt/taxi/prod/{auth-service,driver-service,order-service,admin-service}
mkdir -p /opt/taxi/dev/{auth-service,driver-service,order-service,admin-service}
chmod -R 755 /opt/taxi

# Копирование SSL сертификатов
echo "🔒 Настройка SSL..."
if [ -f "$(dirname "$0")/ssl/xhap.ru.key" ] && [ -f "$(dirname "$0")/ssl/xhap.ru.crt" ]; then
    cp "$(dirname "$0")/ssl/xhap.ru.key" /opt/taxi/ssl/
    cp "$(dirname "$0")/ssl/xhap.ru.crt" /opt/taxi/ssl/
    chmod 600 /opt/taxi/ssl/xhap.ru.key
    chmod 644 /opt/taxi/ssl/xhap.ru.crt
    echo "✅ SSL сертификаты скопированы"
else
    echo "⚠️  SSL сертификаты не найдены, пропускаем..."
fi

echo ""
echo "✅ Установка завершена!"
echo ""
echo "Проверка установки:"
echo "  Docker: $(docker --version)"
echo "  Docker Compose: $(docker-compose --version)"
echo "  Nginx: $(nginx -v 2>&1)"
echo ""
echo "Следующие шаги:"
echo "  1. Настройте переменные окружения в deploy/env/.env.prod"
echo "  2. Запустите ./deploy/deploy.sh prod"


