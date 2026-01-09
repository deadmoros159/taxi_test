from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей в системе"""
    PASSENGER = "passenger"      # Обычный пользователь - может заказывать такси
    DRIVER = "driver"            # Водитель - может принимать заказы
    DISPATCHER = "dispatcher"    # Диспетчер - управление водителями, регистрация водителей
    ADMIN = "admin"              # Админ - полный доступ ко всем процессам

