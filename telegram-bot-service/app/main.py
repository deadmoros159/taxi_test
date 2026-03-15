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

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def on_startup_bot(bot: Bot) -> None:
    webhook_url = f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}"
    use_webhook = settings.WEBHOOK_HOST.startswith("https://")
    
    if not use_webhook:
        logger.warning(
            f"⚠️  Webhook URL не HTTPS ({webhook_url}). "
            f"Webhook не будет установлен. Используйте HTTPS URL для production."
        )
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен (без webhook): @{bot_info.username} ({bot_info.first_name})")
        return
    
    try:
        secret_token = settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None
        await bot.set_webhook(
            url=webhook_url,
            secret_token=secret_token,
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username} ({bot_info.first_name})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при установке webhook: {e}", exc_info=True)
        raise


async def on_shutdown_bot(bot: Bot) -> None:
    if settings.WEBHOOK_HOST.startswith("https://"):
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("🔴 Webhook удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении webhook: {e}", exc_info=True)


bot: Bot = None
dp: Dispatcher = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    from aiogram.client.default import DefaultBotProperties
    
    # Startup
    logger.info("=" * 50)
    logger.info("Starting Telegram Bot Service")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Webhook Host: {settings.WEBHOOK_HOST}")
    logger.info(f"Webhook Path: {settings.WEBHOOK_PATH}")
    
    try:
        logger.info("Initializing bot and dispatcher...")
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher()
        
        logger.info("Registering routers...")
        dp.include_router(auth_router)
        
        logger.info("Setting up webhook...")
        await on_startup_bot(bot)
        
        logger.info("=" * 50)
        logger.info("Telegram Bot Service started successfully!")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"ERROR during startup: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Telegram Bot Service")
    try:
        await on_shutdown_bot(bot)
        if bot:
            await bot.session.close()
    except Exception as e:
        logger.error(f"ERROR during shutdown: {e}", exc_info=True)


def create_fastapi_app() -> FastAPI:
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
    
    cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [str(settings.CORS_ORIGINS)]
    cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS
    allow_methods = list(settings.CORS_ALLOW_METHODS) if isinstance(settings.CORS_ALLOW_METHODS, (list, tuple)) else ["*"]
    allow_headers = list(settings.CORS_ALLOW_HEADERS) if isinstance(settings.CORS_ALLOW_HEADERS, (list, tuple)) else ["*"]

    if "*" in cors_origins:
        cors_allow_credentials = False

    cors_kwargs = dict(
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=["X-Correlation-ID"],
    )
    if settings.ENVIRONMENT == "development":
        cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

    app.add_middleware(CORSMiddleware, **cors_kwargs)
    
    @app.post(settings.WEBHOOK_PATH)
    async def webhook_endpoint(request: Request):
        global bot, dp
        
        if not bot or not dp:
            from fastapi import status
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Bot not initialized"}
            )
        
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
        
        body = await request.json()
        update_type = "callback_query" if "callback_query" in body else ("message" if "message" in body else list(body.keys()))
        logger.info(f"Webhook received: {update_type}")
        try:
            from aiogram.types import Update
            update = Update(**body)
            if update.callback_query:
                logger.info(f"CallbackQuery: data={update.callback_query.data!r}")
            elif update.message:
                logger.info(f"Message: text={getattr(update.message, 'text', None)!r}")
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
    
    @app.get("/health")
    async def health_check_endpoint():
        return {
            "status": "healthy",
            "service": "telegram-bot-service",
            "version": "1.0.0",
            "webhook_configured": settings.WEBHOOK_HOST is not None and settings.WEBHOOK_HOST.startswith("https://")
        }
    
    @app.get("/")
    async def root_endpoint():
        return {
            "service": "Telegram Bot Service",
            "version": "1.0.0",
            "webhook_url": f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}",
            "health": "/health",
            "docs": "/docs"
        }
    
    from app.api.v1.endpoints import auth as auth_endpoints
    from app.api.v1.endpoints import telegram as telegram_endpoints
    from app.api.v1.endpoints import app_redirect as app_redirect_endpoints

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

    app.include_router(
        app_redirect_endpoints.router,
        prefix="/app",
        tags=["app-redirect"]
    )
    
    return app


async def run_polling():
    from aiogram.client.default import DefaultBotProperties
    
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    dp.include_router(auth_router)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен (polling): @{bot_info.username} ({bot_info.first_name})")
        logger.info("📡 Режим: Polling (для локальной разработки)")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Error running polling: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()


async def run_webhook_server():
    app = create_fastapi_app()
    
    import uvicorn
    
    logger.info(f"✅ FastAPI server starting on {settings.HOST}:{settings.PORT}")
    logger.info(f"📚 Swagger UI: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"🔗 Auth Service URL: {settings.AUTH_SERVICE_URL}")
    logger.info(f"📡 Webhook URL: {settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    
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
        use_webhook = settings.WEBHOOK_HOST.startswith("https://")
        if use_webhook:
            logger.info("🌐 Режим: Webhook (production)")
            asyncio.run(run_webhook_server())
        else:
            logger.info("🔄 Режим: Polling (локальная разработка)")
            asyncio.run(run_polling())
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
