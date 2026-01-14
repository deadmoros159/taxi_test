# Исправление проблем деплоя

## Проблемы

1. **SSL сертификат** - Nginx использует самоподписанный сертификат
2. **Миграции** - ошибки при создании уже существующих объектов

## Решения

### 1. Проверка SSL на сервере

```bash
# Проверьте, что сертификаты на месте
ls -la /opt/taxi/ssl/

# Должны быть:
# xhap.ru.key (600)
# xhap.ru.crt (644)

# Проверьте конфигурацию Nginx
nginx -t

# Перезагрузите Nginx
systemctl reload nginx
# или
nginx -s reload
```

### 2. Обновление кода на сервере

```bash
cd /opt/taxi/taxi_back
git pull
cd deploy
./deploy.sh prod restart
```

### 3. Проверка после исправлений

```bash
# Проверьте статус контейнеров
docker ps

# Проверьте health endpoints
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Проверьте через Nginx (с игнорированием SSL для теста)
curl -k https://xhap.ru/auth/health
```

## Что исправлено

1. **auth-service**: Миграции теперь игнорируют ошибки "already exists"
2. **order-service**: Добавлена проверка существования enum перед созданием
3. **docker-compose**: Убрано предупреждение о `version`


