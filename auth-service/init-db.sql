-- Инициализационный SQL скрипт для auth-service
-- Этот файл выполняется при первом запуске PostgreSQL контейнера

-- Создание пользователя auth_user с паролем из переменной окружения
-- Пароль должен совпадать с POSTGRES_PASSWORD из .env
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'auth_user') THEN
        -- Пароль должен быть экранирован для SQL
        CREATE USER auth_user WITH PASSWORD 'Db7x!A@9pL92qR$5vN^8cM&3bV*6y';
        ALTER USER auth_user CREATEDB;
    END IF;
END
$$;

-- Предоставление прав на базу данных
GRANT ALL PRIVILEGES ON DATABASE auth_db TO auth_user;

-- Можно добавить начальные данные или настройки БД здесь
-- Например:
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

