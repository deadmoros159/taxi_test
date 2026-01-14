#!/bin/bash

# Скрипт проверки DNS настроек
# Использование: ./check-dns.sh

echo "🔍 Проверка DNS настроек для xhap.ru"
echo ""

DOMAIN="xhap.ru"
EXPECTED_IP="102.214.69.160"

check_dns() {
    local host=$1
    local expected=$2
    
    echo "Проверка: $host"
    
    # Проверяем через dig
    if command -v dig &> /dev/null; then
        result=$(dig +short $host 2>/dev/null | head -1)
        if [ "$result" == "$expected" ]; then
            echo "  ✅ DNS настроен правильно: $result"
        elif [ -n "$result" ]; then
            echo "  ⚠️  DNS указывает на другой IP: $result (ожидается: $expected)"
        else
            echo "  ❌ DNS запись не найдена"
        fi
    else
        echo "  ⚠️  dig не установлен, используем nslookup"
        result=$(nslookup $host 2>/dev/null | grep -A 1 "Name:" | tail -1 | awk '{print $2}')
        if [ "$result" == "$expected" ]; then
            echo "  ✅ DNS настроен правильно: $result"
        else
            echo "  ⚠️  Результат: $result (ожидается: $expected)"
        fi
    fi
    echo ""
}

# Проверяем основные записи
check_dns "$DOMAIN" "$EXPECTED_IP"
check_dns "www.$DOMAIN" "$EXPECTED_IP"
check_dns "dev.$DOMAIN" "$EXPECTED_IP"

echo "🌐 Проверка через онлайн сервисы:"
echo "  - https://dnschecker.org/#A/$DOMAIN"
echo "  - https://www.whatsmydns.net/#A/$DOMAIN"
echo ""
echo "💡 Если DNS не настроен, см. инструкцию в DNS_SETUP.md"


