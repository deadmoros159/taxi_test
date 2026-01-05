"""
Circuit Breaker для защиты от каскадных сбоев
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Сбой, запросы блокируются
    HALF_OPEN = "half_open"  # Тестирование восстановления


class CircuitBreaker:
    """
    Circuit Breaker pattern для защиты от каскадных сбоев
    
    Принцип работы:
    - CLOSED: Все запросы проходят
    - OPEN: После N ошибок, все запросы блокируются на timeout
    - HALF_OPEN: После timeout, один запрос проходит для проверки
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: str = "circuit_breaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнить функцию через circuit breaker
        
        Args:
            func: Асинхронная функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            CircuitBreakerOpenError: Если circuit breaker открыт
            Exception: Оригинальная ошибка функции
        """
        async with self._lock:
            # Проверяем состояние
            if self.state == CircuitState.OPEN:
                if time.time() - (self.last_failure_time or 0) < self.recovery_timeout:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {self.recovery_timeout}s"
                    )
                else:
                    # Переходим в HALF_OPEN для тестирования
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.name}' moved to HALF_OPEN")
            
            # Выполняем функцию
            try:
                result = await func(*args, **kwargs)
                # Успех - сбрасываем счетчик
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' recovered, moved to CLOSED")
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0
                
                return result
                
            except self.expected_exception as e:
                # Ошибка - увеличиваем счетчик
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.error(
                        f"Circuit breaker '{self.name}' opened after {self.failure_count} failures"
                    )
                
                raise
    
    def reset(self):
        """Сбросить circuit breaker в начальное состояние"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' reset")


class CircuitBreakerOpenError(Exception):
    """Ошибка когда circuit breaker открыт"""
    pass

