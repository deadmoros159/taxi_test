FROM python:3.11-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем shared library requirements
COPY shared/requirements.txt /tmp/shared_requirements.txt

# Копируем зависимости сервиса
COPY driver-service/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt

# Production образ
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем curl для health checks
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем Python зависимости из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Создаем не-root пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

# Копируем shared library
COPY --chown=appuser:appuser shared /app/shared

# Копируем код приложения
COPY --chown=appuser:appuser driver-service /app

# Переключаемся на не-root пользователя
USER appuser

# Запускаем приложение через uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
