"""
Инициализация и регистрация всех обработчиков бота.
"""

from aiogram import Dispatcher

from .basic import register_basic_handlers
from .website_management import register_website_handlers
from .admin import register_admin_handlers


def register_handlers(dp: Dispatcher) -> None:
    """Регистрация всех обработчиков"""
    # Базовые команды (start, help, settings)
    register_basic_handlers(dp)
    
    # Управление сайтами
    register_website_handlers(dp)
    
    # Административные команды
    register_admin_handlers(dp)