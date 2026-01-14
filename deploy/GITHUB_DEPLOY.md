# Деплой через GitHub

## Настройка на сервере

### 1. Подключитесь к серверу

```bash
ssh root@102.214.69.160
```

### 2. Клонируйте репозиторий

```bash
cd /opt/taxi
git clone git@github.com:ВАШ_USERNAME/ВАШ_REPO.git .
```

Или если используете HTTPS (понадобится токен):

```bash
git clone https://github.com/ВАШ_USERNAME/ВАШ_REPO.git .
```

### 3. Настройте репозиторий (автоматически)

```bash
cd /opt/taxi/deploy
bash setup-github.sh git@github.com:ВАШ_USERNAME/ВАШ_REPO.git
```

## Настройка переменных окружения

```bash
cd /opt/taxi/deploy/env
cp .env.prod.example .env.prod
nano .env.prod  # Заполните все значения
```

**Важно:** Файл `.env.prod` НЕ должен быть в git (добавьте в `.gitignore`)

## Настройка SSL

```bash
mkdir -p /opt/taxi/ssl
# Скопируйте xhap.ru.key и xhap.ru.crt в /opt/taxi/ssl/
nano /opt/taxi/ssl/xhap.ru.key
nano /opt/taxi/ssl/xhap.ru.crt
chmod 600 /opt/taxi/ssl/xhap.ru.key
chmod 644 /opt/taxi/ssl/xhap.ru.crt
```

## Первый деплой

```bash
cd /opt/taxi/deploy
bash install.sh          # Установка зависимостей
bash setup-nginx.sh      # Настройка Nginx
./deploy.sh prod start   # Запуск сервисов
```

## Обновление кода

### Вариант 1: Вручную на сервере

```bash
cd /opt/taxi/deploy
./update-from-github.sh prod
./deploy.sh prod restart
```

### Вариант 2: Автоматически через GitHub Actions

1. Добавьте SSH ключ сервера в GitHub Secrets:
   - Settings → Secrets and variables → Actions
   - New repository secret
   - Name: `SERVER_SSH_KEY`
   - Value: приватный ключ с сервера (`/root/.ssh/id_rsa` или аналогичный)

2. При push в `main`/`master` автоматически запустится деплой

## Структура .gitignore

Убедитесь, что в `.gitignore` есть:

```
# Переменные окружения
**/.env
**/.env.prod
**/.env.dev
deploy/env/.env.*

# SSL сертификаты
deploy/ssl/*.key
deploy/ssl/*.crt
deploy/ssl/*.pem

# Логи
*.log
```

## Полезные команды

```bash
# Обновить код и перезапустить
cd /opt/taxi/deploy
./update-from-github.sh prod
./deploy.sh prod restart

# Просмотр логов
./deploy.sh prod logs

# Статус сервисов
docker ps
```


