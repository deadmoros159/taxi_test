# Деплой микросервисной архитектуры такси

## Структура

```
deploy/
├── install.sh              # Скрипт установки всех зависимостей
├── deploy.sh               # Скрипт деплоя
├── ssl/
│   ├── xhap.ru.key         # Приватный ключ SSL
│   └── xhap.ru.crt         # SSL сертификат
├── nginx/
│   ├── nginx.conf          # Основная конфигурация Nginx
│   ├── prod.conf           # Production конфигурация
│   └── dev.conf            # Development конфигурация
├── docker-compose.prod.yml # Production Docker Compose
├── docker-compose.dev.yml  # Development Docker Compose
├── monitoring/
│   └── docker-compose.monitoring.yml
└── env/
    ├── .env.prod           # Production переменные окружения
    └── .env.dev            # Development переменные окружения
```

## Домены

### Production
- `https://xhap.ru/auth` - Auth Service
- `https://xhap.ru/driver` - Driver Service
- `https://xhap.ru/order` - Order Service
- `https://xhap.ru/admin` - Admin Service

### Development
- `https://dev.xhap.ru/auth` - Auth Service (dev)
- `https://dev.xhap.ru/driver` - Driver Service (dev)
- `https://dev.xhap.ru/order` - Order Service (dev)
- `https://dev.xhap.ru/admin` - Admin Service (dev)

## Мониторинг
- Grafana: `https://xhap.ru/grafana`
- Prometheus: `https://xhap.ru/prometheus`

## Быстрый старт

1. Скопируйте проект на сервер
2. Запустите `./deploy/install.sh`
3. Настройте переменные окружения в `deploy/env/.env.prod`
4. Запустите `./deploy/deploy.sh prod`

