"""
Настройка логирования для приложения.
"""

import logging
import logging.config
import os
from ..config import LOGGING_CONFIG


def setup_logging() -> None:
    """Настройка системы логирования"""
    # Создаем директорию для логов если её нет
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Применяем конфигурацию логирования
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Получаем логгер
    logger = logging.getLogger(__name__)
    logger.info("Система логирования инициализирована")