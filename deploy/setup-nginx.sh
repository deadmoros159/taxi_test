#!/bin/bash

# Скрипт настройки Nginx
# Запускать от root: sudo bash setup-nginx.sh

set -e

echo "🌐 Настройка Nginx..."

# Копируем конфигурации
cp nginx/nginx.conf /etc/nginx/nginx.conf
cp nginx/prod.conf /etc/nginx/sites-available/xhap.ru
cp nginx/dev.conf /etc/nginx/sites-available/dev.xhap.ru

# Создаем символические ссылки
ln -sf /etc/nginx/sites-available/xhap.ru /etc/nginx/sites-enabled/xhap.ru
ln -sf /etc/nginx/sites-available/dev.xhap.ru /etc/nginx/sites-enabled/dev.xhap.ru

# Удаляем дефолтную конфигурацию
rm -f /etc/nginx/sites-enabled/default

# Проверяем конфигурацию
echo "🔍 Проверка конфигурации Nginx..."
nginx -t

# Перезапускаем Nginx
echo "🔄 Перезапуск Nginx..."
systemctl restart nginx

echo "✅ Nginx настроен и запущен"
echo ""
echo "Доступные эндпоинты:"
echo "  Production:"
echo "    - https://xhap.ru/auth"
echo "    - https://xhap.ru/driver"
echo "    - https://xhap.ru/order"
echo "    - https://xhap.ru/admin"
echo ""
echo "  Development:"
echo "    - https://dev.xhap.ru/auth"
echo "    - https://dev.xhap.ru/driver"
echo "    - https://dev.xhap.ru/order"
echo "    - https://dev.xhap.ru/admin"

