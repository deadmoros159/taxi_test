FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создаем не-root пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Переключаемся на не-root пользователя
USER appuser

# Устанавливаем PYTHONPATH чтобы Python мог найти модуль app
ENV PYTHONPATH=/app

# Запускаем Telegram бота через uvicorn (FastAPI + webhook)
CMD ["uvicorn", "app.main:create_fastapi_app", "--host", "0.0.0.0", "--port", "8004", "--factory"]

