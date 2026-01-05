-- Инициализационный SQL скрипт для driver-service

-- Создание пользователя для driver_db
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'driver_user') THEN
        CREATE USER driver_user WITH PASSWORD '${POSTGRES_PASSWORD}';
        ALTER USER driver_user CREATEDB;
    END IF;
END
$$;

-- Предоставление прав на базу данных
GRANT ALL PRIVILEGES ON DATABASE driver_db TO driver_user;

