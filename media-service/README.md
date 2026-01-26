# Media Service

Сервис для загрузки и управления медиа-файлами (изображения, документы).

## Возможности

- Загрузка файлов с ограничением 5 МБ
- Хранение файлов в MinIO (S3-совместимое хранилище)
- Авторизация через токен
- Контроль доступа (пользователь может получить только свои файлы, админы - любые)
- Метаданные файлов хранятся в PostgreSQL

## API Endpoints

### POST /api/v1/media/upload
Загрузить файл (требуется авторизация).

**Ограничения:**
- Максимальный размер: 5 МБ
- Разрешенные типы: изображения (JPEG, PNG, GIF, WebP), PDF, документы Word

**Ответ:**
```json
{
  "media_id": 123,
  "filename": "user_1/uuid.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 102400,
  "url": "/api/v1/media/123",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### GET /api/v1/media/{media_id}
Получить файл по ID (требуется авторизация).

**Права доступа:**
- Пользователь может получить только свои файлы
- Админы могут получить любые файлы

### GET /api/v1/media/{media_id}/info
Получить метаданные файла (требуется авторизация).

### DELETE /api/v1/media/{media_id}
Удалить файл (требуется авторизация).

**Права доступа:**
- Пользователь может удалить только свои файлы
- Админы могут удалить любые файлы

## Конфигурация

### Переменные окружения

```env
# Database
POSTGRES_SERVER=postgres-media
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=media_db
POSTGRES_PORT=5432

# Auth Service
AUTH_SERVICE_URL=http://auth-service:8000

# MinIO (S3-compatible storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=media
MINIO_SECURE=false

# File Upload Settings
MAX_FILE_SIZE_MB=5
```

## Использование

### Загрузка файла

```bash
curl -X POST "http://localhost:8003/api/v1/media/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/file.jpg"
```

### Получение файла

```bash
curl -X GET "http://localhost:8003/api/v1/media/123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output file.jpg
```

### Использование в других сервисах

В других сервисах (например, `driver-service`) храните только `media_id`:

```python
# В модели водителя
license_photo_id: Optional[int] = None  # ID файла из media-service

# При запросе данных водителя
if driver.license_photo_id:
    # Фронт делает отдельный запрос:
    # GET /api/v1/media/{driver.license_photo_id}
```

## MinIO

MinIO - это S3-совместимое хранилище, которое можно использовать локально или в production.

### Доступ к MinIO Console

После запуска docker-compose, MinIO Console доступна по адресу:
- http://localhost:9001
- Логин: `minioadmin` (или значение из `MINIO_ACCESS_KEY`)
- Пароль: `minioadmin` (или значение из `MINIO_SECRET_KEY`)

### Миграция на AWS S3

Для миграции на AWS S3 достаточно изменить переменные окружения:

```env
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=YOUR_AWS_ACCESS_KEY
MINIO_SECRET_KEY=YOUR_AWS_SECRET_KEY
MINIO_BUCKET_NAME=your-bucket-name
MINIO_SECURE=true
```

Код останется без изменений, так как MinIO клиент совместим с S3.

