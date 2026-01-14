# 📋 Сводка по деплою

## ✅ Что подготовлено

### Структура файлов

```
deploy/
├── install.sh                    # Установка всех зависимостей
├── deploy.sh                     # Управление сервисами (start/stop/restart/logs)
├── full-deploy.sh                # Полный деплой с нуля
├── setup-nginx.sh                # Настройка Nginx
├── README.md                     # Общая информация
├── DEPLOYMENT.md                 # Подробная инструкция
├── QUICK_START.md                # Быстрый старт
├── SUMMARY.md                    # Этот файл
│
├── docker-compose.prod.yml       # Production окружение
├── docker-compose.dev.yml        # Development окружение
│
├── nginx/
│   ├── nginx.conf                # Основная конфигурация
│   ├── prod.conf                 # Production виртуальный хост
│   └── dev.conf                  # Development виртуальный хост
│
├── monitoring/
│   ├── docker-compose.monitoring.yml
│   ├── prometheus/prometheus.yml
│   ├── loki/loki-config.yml
│   └── promtail/promtail-config.yml
│
└── env/
    ├── .env.prod.example         # Пример для production
    └── .env.dev.example          # Пример для development
```

## 🌐 Домены и эндпоинты

### Production
- `https://xhap.ru/auth` → Auth Service (порт 8000)
- `https://xhap.ru/driver` → Driver Service (порт 8001)
- `https://xhap.ru/order` → Order Service (порт 8002)
- `https://xhap.ru/admin` → Admin Service (порт 8003)
- `https://xhap.ru/grafana` → Grafana (мониторинг)
- `https://xhap.ru/prometheus` → Prometheus (метрики)

### Development
- `https://dev.xhap.ru/auth` → Auth Service (порт 9000)
- `https://dev.xhap.ru/driver` → Driver Service (порт 9001)
- `https://dev.xhap.ru/order` → Order Service (порт 9002)
- `https://dev.xhap.ru/admin` → Admin Service (порт 9003)

## 🚀 Быстрый деплой

### 1. Подключение к серверу
```bash
ssh root@102.214.69.160
```

### 2. Копирование проекта
```bash
# С вашего компьютера
cd /Users/rustam/Desktop/taxi
scp -r deploy root@102.214.69.160:/opt/taxi/
scp -r auth-service driver-service order-service admin-service shared root@102.214.69.160:/opt/taxi/
```

### 3. Полный деплой
```bash
# На сервере
cd /opt/taxi/deploy
bash full-deploy.sh prod
```

## 📝 Что нужно сделать перед деплоем

1. ✅ **SSL сертификаты** - уже есть (xhap.ru.key и xhap.ru.crt)
2. ⚠️ **DNS настройки** - добавьте A записи:
   - `xhap.ru` → `102.214.69.160`
   - `dev.xhap.ru` → `102.214.69.160` (опционально)
3. ⚠️ **Переменные окружения** - создайте `env/.env.prod`:
   ```bash
   cd /opt/taxi/deploy/env
   cp .env.prod.example .env.prod
   nano .env.prod  # Заполните все значения
   ```
4. ⚠️ **Секретные ключи** - сгенерируйте новые для production:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

## 🔧 Управление сервисами

```bash
cd /opt/taxi/deploy

# Production
./deploy.sh prod start      # Запуск
./deploy.sh prod stop       # Остановка
./deploy.sh prod restart    # Перезапуск
./deploy.sh prod logs       # Логи

# Development
./deploy.sh dev start       # Запуск
./deploy.sh dev stop        # Остановка
./deploy.sh dev restart     # Перезапуск
./deploy.sh dev logs        # Логи
```

## 📊 Мониторинг

```bash
cd /opt/taxi/deploy/monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

- Grafana: `https://xhap.ru/grafana` (admin / пароль из .env.prod)
- Prometheus: `https://xhap.ru/prometheus`

## 🔍 Проверка работы

```bash
# Статус контейнеров
docker ps

# Health checks
curl https://xhap.ru/auth/health
curl https://xhap.ru/driver/health
curl https://xhap.ru/order/health
curl https://xhap.ru/admin/health

# Логи
docker logs taxi-auth-service-prod
docker logs taxi-driver-service-prod
```

## 📚 Документация

- `QUICK_START.md` - быстрый старт
- `DEPLOYMENT.md` - подробная инструкция
- `README.md` - общая информация

## ⚠️ Важные замечания

1. **Безопасность**: 
   - Используйте сильные пароли для production
   - Не коммитьте `.env.prod` в git
   - Храните SSL ключи в безопасности

2. **Ресурсы сервера**:
   - 2 ГБ RAM может быть мало для всех сервисов
   - Рекомендуется минимум 4 ГБ для production
   - Мониторинг потребляет дополнительную память

3. **Резервное копирование**:
   - Настройте автоматические бэкапы БД
   - Храните бэкапы отдельно от сервера

4. **Обновления**:
   - Тестируйте обновления на dev окружении
   - Используйте blue-green deployment для production

## 🆘 Поддержка

При проблемах проверьте:
1. Логи контейнеров: `docker logs <container_name>`
2. Логи Nginx: `tail -f /var/log/nginx/error.log`
3. Статус сервисов: `docker ps`
4. Использование ресурсов: `docker stats`


