"""
Correlation ID для отслеживания запросов между сервисами
"""
import uuid
from typing import Optional
from contextvars import ContextVar

# Context variable для хранения correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> Optional[str]:
    """Получить текущий correlation ID"""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Установить correlation ID
    
    Args:
        correlation_id: ID для установки. Если None, генерируется новый
        
    Returns:
        Установленный correlation ID
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    correlation_id_var.set(correlation_id)
    return correlation_id


def generate_correlation_id() -> str:
    """Сгенерировать новый correlation ID"""
    return set_correlation_id()

