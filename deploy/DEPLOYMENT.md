# Инструкция по деплою

## Подготовка сервера

### 1. Подключение к серверу

```bash
ssh root@102.214.69.160
```

### 2. Установка зависимостей

```bash
# Клонируйте репозиторий или скопируйте файлы на сервер
cd /opt/taxi
git clone <your-repo-url> .  # или скопируйте файлы через scp

# Запустите скрипт установки
cd deploy
bash install.sh
```

### 3. Настройка SSL сертификатов

```bash
# Скопируйте SSL сертификаты (если еще не скопированы)
mkdir -p /opt/taxi/ssl
# Скопируйте xhap.ru.key и xhap.ru.crt в /opt/taxi/ssl/
chmod 600 /opt/taxi/ssl/xhap.ru.key
chmod 644 /opt/taxi/ssl/xhap.ru.crt
```

### 4. Настройка переменных окружения

```bash
cd /opt/taxi/deploy/env
cp .env.prod.example .env.prod
cp .env.dev.example .env.dev

# Отредактируйте файлы и заполните все значения
nano .env.prod
nano .env.dev
```

**Важно:** Сгенерируйте новые секретные ключи для production:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Настройка DNS

Настройте DNS записи для домена `xhap.ru`:
- A запись: `xhap.ru` -> `102.214.69.160`
- A запись: `dev.xhap.ru` -> `102.214.69.160` (опционально)

### 6. Настройка Nginx

```bash
cd /opt/taxi/deploy
bash setup-nginx.sh
```

## Деплой

### Production

```bash
cd /opt/taxi/deploy
./deploy.sh prod start
```

### Development

```bash
cd /opt/taxi/deploy
./deploy.sh dev start
```

## Управление сервисами

```bash
# Запуск
./deploy.sh prod start
./deploy.sh dev start

# Остановка
./deploy.sh prod stop
./deploy.sh dev stop

# Перезапуск
./deploy.sh prod restart
./deploy.sh dev restart

# Просмотр логов
./deploy.sh prod logs
./deploy.sh dev logs
```

## Мониторинг

### Запуск мониторинга

```bash
cd /opt/taxi/deploy/monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### Доступ к Grafana

- URL: `https://xhap.ru/grafana` (через Nginx)
- Или напрямую: `http://102.214.69.160:3000`
- Логин: `admin`
- Пароль: из переменной `GRAFANA_PASSWORD`

### Доступ к Prometheus

- URL: `https://xhap.ru/prometheus` (через Nginx)
- Или напрямую: `http://102.214.69.160:9090`

## Проверка работы

```bash
# Проверка статуса контейнеров
docker ps

# Проверка логов
docker logs taxi-auth-service-prod
docker logs taxi-driver-service-prod

# Проверка health checks
curl https://xhap.ru/auth/health
curl https://xhap.ru/driver/health
curl https://xhap.ru/order/health
curl https://xhap.ru/admin/health
```

## Обновление кода

```bash
# Остановите сервисы
./deploy.sh prod stop

# Обновите код (git pull или scp)
git pull  # или другой способ

# Пересоберите и запустите
./deploy.sh prod start
```

## Резервное копирование

```bash
# Бэкап баз данных
docker exec taxi-postgres-auth-prod pg_dump -U postgres auth_db > backup_auth_$(date +%Y%m%d).sql
docker exec taxi-postgres-driver-prod pg_dump -U postgres driver_db > backup_driver_$(date +%Y%m%d).sql
docker exec taxi-postgres-order-prod pg_dump -U postgres order_db > backup_order_$(date +%Y%m%d).sql
```

## Troubleshooting

### Проблемы с Nginx

```bash
# Проверка конфигурации
nginx -t

# Перезапуск
systemctl restart nginx

# Просмотр логов
tail -f /var/log/nginx/error.log
```

### Проблемы с Docker

```bash
# Просмотр логов контейнера
docker logs <container_name>

# Перезапуск контейнера
docker restart <container_name>

# Просмотр использования ресурсов
docker stats
```

### Проблемы с SSL

```bash
# Проверка сертификата
openssl x509 -in /opt/taxi/ssl/xhap.ru.crt -text -noout

# Проверка ключа
openssl rsa -in /opt/taxi/ssl/xhap.ru.key -check
```

