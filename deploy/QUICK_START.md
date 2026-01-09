# Быстрый старт деплоя

## Шаг 1: Подключение к серверу

```bash
ssh root@102.214.69.160
```

## Шаг 2: Копирование проекта на сервер

С вашего локального компьютера:

```bash
# Создайте архив проекта (исключая ненужные файлы)
cd /Users/rustam/Desktop/taxi
tar --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.git' --exclude='node_modules' \
    -czf taxi-deploy.tar.gz .

# Скопируйте на сервер
scp taxi-deploy.tar.gz root@102.214.69.160:/opt/taxi/
```

На сервере:

```bash
cd /opt/taxi
tar -xzf taxi-deploy.tar.gz
rm taxi-deploy.tar.gz
```

## Шаг 3: Установка зависимостей

```bash
cd /opt/taxi/deploy
bash install.sh
```

## Шаг 4: Настройка SSL

```bash
# Скопируйте SSL файлы в /opt/taxi/ssl/
# (если еще не скопированы через scp)
mkdir -p /opt/taxi/ssl
# Вставьте содержимое xhap.ru.key и xhap.ru.crt
nano /opt/taxi/ssl/xhap.ru.key
nano /opt/taxi/ssl/xhap.ru.crt

chmod 600 /opt/taxi/ssl/xhap.ru.key
chmod 644 /opt/taxi/ssl/xhap.ru.crt
```

## Шаг 5: Настройка переменных окружения

```bash
cd /opt/taxi/deploy/env
cp .env.prod.example .env.prod
nano .env.prod  # Заполните все значения
```

**Важно:** Сгенерируйте секретные ключи:
```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_REFRESH_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

## Шаг 6: Настройка DNS

**Подробная инструкция:** См. `DNS_SETUP.md`

В панели управления доменом `xhap.ru` добавьте:
- A запись: `@` (или `xhap.ru`) -> `102.214.69.160`
- A запись: `www` -> `102.214.69.160` (опционально)
- A запись: `dev` -> `102.214.69.160` (опционально, для dev окружения)

**Проверка DNS:**
```bash
dig xhap.ru +short  # Должно вернуть: 102.214.69.160
```

Подождите распространения DNS (5-30 минут, иногда до 1 часа).

## Шаг 7: Настройка Nginx

```bash
cd /opt/taxi/deploy
bash setup-nginx.sh
```

## Шаг 8: Деплой Production

```bash
cd /opt/taxi/deploy
./deploy.sh prod start
```

## Шаг 9: Проверка

```bash
# Проверка статуса
docker ps

# Проверка health checks
curl https://xhap.ru/auth/health
curl https://xhap.ru/driver/health
curl https://xhap.ru/order/health
curl https://xhap.ru/admin/health
```

## Шаг 10: Запуск мониторинга (опционально)

```bash
cd /opt/taxi/deploy/monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

Доступ:
- Grafana: `https://xhap.ru/grafana` (логин: admin, пароль из .env.prod)
- Prometheus: `https://xhap.ru/prometheus`

## Готово! 🎉

Ваши сервисы доступны по адресам:
- `https://xhap.ru/auth`
- `https://xhap.ru/driver`
- `https://xhap.ru/order`
- `https://xhap.ru/admin`

