import logging
import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
# aiogram 3.4.1 не имеет webhook.fastapi, используем aiohttp интеграцию
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.handlers.auth import router as auth_router
from pydantic import SecretStr

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def on_startup_bot(bot: Bot) -> None:
    """Выполняется при старте приложения"""
    webhook_url = f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}"
    
    # Проверяем, является ли URL HTTPS (Telegram требует HTTPS для webhook)
    use_webhook = settings.WEBHOOK_HOST.startswith("https://")
    
    if not use_webhook:
        logger.warning(
            f"⚠️  Webhook URL не HTTPS ({webhook_url}). "
            f"Webhook не будет установлен. Используйте HTTPS URL для production."
        )
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен (без webhook): @{bot_info.username} ({bot_info.first_name})")
        return
    
    try:
        # Устанавливаем webhook только если URL HTTPS
        secret_token = settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None
        await bot.set_webhook(
            url=webhook_url,
            secret_token=secret_token,
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username} ({bot_info.first_name})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при установке webhook: {e}", exc_info=True)
        raise


async def on_shutdown_bot(bot: Bot) -> None:
    """Выполняется при остановке бота"""
    # Удаляем webhook только если он был установлен (HTTPS)
    if settings.WEBHOOK_HOST.startswith("https://"):
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("🔴 Webhook удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении webhook: {e}", exc_info=True)


# Глобальные объекты
bot: Bot = None
dp: Dispatcher = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для управления ботом"""
    global bot, dp
    from aiogram.client.default import DefaultBotProperties
    
    # Startup
    logger.info("Starting Telegram Bot Service")
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(auth_router)
    
    # Устанавливаем webhook если нужно
    await on_startup_bot(bot)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Telegram Bot Service")
    await on_shutdown_bot(bot)
    if bot:
        await bot.session.close()


def create_fastapi_app() -> FastAPI:
    """Создание FastAPI приложения с webhook и Swagger"""
    app = FastAPI(
        title="Telegram Bot Service",
        version="1.0.0",
        description="Сервис Telegram бота для авторизации и управления заказами",
        openapi_url="/openapi.json",  # Путь относительно root_path
        docs_url="/docs",
        redoc_url="/redoc",
        root_path="/telegram",  # Префикс для работы через Nginx
        lifespan=lifespan,
    )
    
    # CORS middleware
    cors_origins = settings.CORS_ORIGINS
    cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS

    if "*" in cors_origins:
        cors_allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=["X-Correlation-ID"],
    )
    
    # Webhook endpoint для обработки запросов от Telegram
    @app.post(settings.WEBHOOK_PATH)
    async def webhook_endpoint(request: Request):
        """Endpoint для обработки webhook запросов от Telegram"""
        global bot, dp
        
        if not bot or not dp:
            from fastapi import status
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Bot not initialized"}
            )
        
        # Проверяем secret token если он установлен
        if settings.WEBHOOK_SECRET:
            secret_token = settings.WEBHOOK_SECRET.get_secret_value()
            received_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if received_token != secret_token:
                from fastapi import status
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid secret token"}
                )
        
        # Получаем тело запроса
        body = await request.json()
        
        # Обрабатываем через диспетчер aiogram
        try:
            from aiogram.types import Update
            update = Update(**body)
            # В aiogram 3.4.1 используем feed_update для обработки webhook
            await dp.feed_update(bot, update)
            return {"ok": True}
        except Exception as e:
            logger.error(f"Error processing webhook update: {e}", exc_info=True)
            from fastapi import status
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Error processing update"}
            )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check_endpoint():
        """Health check для Kubernetes и load balancers"""
        return {
            "status": "healthy",
            "service": "telegram-bot-service",
            "version": "1.0.0",
            "webhook_configured": settings.WEBHOOK_HOST is not None and settings.WEBHOOK_HOST.startswith("https://")
        }
    
    # Root endpoint
    @app.get("/")
    async def root_endpoint():
        """Root endpoint"""
        return {
            "service": "Telegram Bot Service",
            "version": "1.0.0",
            "webhook_url": f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}",
            "health": "/health",
            "docs": "/docs"
        }
    
    # Подключаем API роутеры
    from app.api.v1.endpoints import auth as auth_endpoints
    from app.api.v1.endpoints import telegram as telegram_endpoints
    app.include_router(
        auth_endpoints.router,
        prefix="/api/v1/auth/telegram",
        tags=["telegram-auth"]
    )

    app.include_router(
        telegram_endpoints.router,
        prefix="/api/v1/telegram",
        tags=["telegram"]
    )
    
    return app


async def run_polling():
    """Запуск бота в режиме polling (для локальной разработки)"""
    from aiogram.client.default import DefaultBotProperties
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(auth_router)
    
    try:
        # Удаляем webhook если был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен (polling): @{bot_info.username} ({bot_info.first_name})")
        logger.info("📡 Режим: Polling (для локальной разработки)")
        
        # Запускаем polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Error running polling: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()


async def run_webhook_server():
    """Запуск FastAPI сервера с webhook и Swagger"""
    app = create_fastapi_app()
    
    import uvicorn
    
    logger.info(f"✅ FastAPI server starting on {settings.HOST}:{settings.PORT}")
    logger.info(f"📚 Swagger UI: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"🔗 Auth Service URL: {settings.AUTH_SERVICE_URL}")
    logger.info(f"📡 Webhook URL: {settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    
    # Запускаем FastAPI сервер
    config = uvicorn.Config(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        # Проверяем, нужно ли использовать webhook (только для HTTPS)
        use_webhook = settings.WEBHOOK_HOST.startswith("https://")
        
        if use_webhook:
            # Запускаем webhook сервер для production
            logger.info("🌐 Режим: Webhook (production)")
            asyncio.run(run_webhook_server())
        else:
            # Запускаем polling для локальной разработки
            logger.info("🔄 Режим: Polling (локальная разработка)")
            asyncio.run(run_polling())
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
