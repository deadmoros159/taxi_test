"""
Retry Logic с exponential backoff
"""
import asyncio
import random
from typing import Callable, Any, Optional, Type, Tuple
import logging

logger = logging.getLogger(__name__)


class RetryConfig:
    """Конфигурация для retry логики"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions


async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """
    Выполнить функцию с retry и exponential backoff
    
    Args:
        func: Асинхронная функция для выполнения
        config: Конфигурация retry
        *args, **kwargs: Аргументы функции
        
    Returns:
        Результат выполнения функции
        
    Raises:
        Exception: Последняя ошибка после всех попыток
    """
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
            
        except config.retryable_exceptions as e:
            last_exception = e
            
            if attempt == config.max_attempts:
                logger.error(
                    f"Retry exhausted after {attempt} attempts. "
                    f"Last error: {type(e).__name__}: {e}"
                )
                raise
            
            # Вычисляем задержку с exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay
            )
            
            # Добавляем jitter для избежания thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"Attempt {attempt}/{config.max_attempts} failed: {type(e).__name__}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # Не должно сюда дойти, но на всякий случай
    if last_exception:
        raise last_exception
    
    raise RuntimeError("Retry logic error")

