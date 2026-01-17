FROM python:3.11-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

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

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Переключаемся на не-root пользователя
USER appuser

# Запускаем приложение через gunicorn
# Уменьшаем workers с 4 до 2 для экономии памяти на сервере с 2GB RAM
CMD ["gunicorn", \
    "-k", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8003", \
    "--workers", "2", \
    "--threads", "1", \
    "--timeout", "120", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "app.main:app"]


