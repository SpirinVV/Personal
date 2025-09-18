"""
Конфигурация приложения с загрузкой параметров из переменных окружения.
Все настройки загружаются из .env файла через pydantic-settings.
"""

import os
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot настройки
    bot_token: str = Field(..., env="BOT_TOKEN")
    
    # База данных
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_name: str = Field(default="website_monitor", env="DB_NAME")
    db_user: str = Field(default="monitor_user", env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    # Настройки мониторинга
    default_check_interval: int = Field(default=300, env="DEFAULT_CHECK_INTERVAL")
    request_timeout: int = Field(default=10, env="REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    max_concurrent_checks: int = Field(default=50, env="MAX_CONCURRENT_CHECKS")
    batch_size: int = Field(default=100, env="BATCH_SIZE")
    
    # Настройки уведомлений
    notification_delay: int = Field(default=60, env="NOTIFICATION_DELAY")
    weekly_report_day: int = Field(default=0, env="WEEKLY_REPORT_DAY")
    weekly_report_hour: int = Field(default=9, env="WEEKLY_REPORT_HOUR")
    
    # Логирование
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # Безопасность
    allowed_admins: List[int] = Field(default_factory=list, env="ALLOWED_ADMINS")
    
    # Настройки Redis (если потребуется в будущем)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("database_url", pre=True, always=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        """Собираем URL подключения к БД если он не задан явно"""
        if isinstance(v, str) and v:
            return v
        
        return (
            f"postgresql+asyncpg://"
            f"{values.get('db_user')}:"
            f"{values.get('db_password')}@"
            f"{values.get('db_host')}:"
            f"{values.get('db_port')}/"
            f"{values.get('db_name')}"
        )
    
    @validator("allowed_admins", pre=True)
    def parse_admin_ids(cls, v) -> List[int]:
        """Парсим список ID администраторов из строки"""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        elif isinstance(v, list):
            return [int(x) for x in v if isinstance(x, (int, str)) and str(x).isdigit()]
        return []
    
    @validator("weekly_report_day")
    def validate_report_day(cls, v: int) -> int:
        """Проверяем корректность дня недели"""
        if not 0 <= v <= 6:
            raise ValueError("weekly_report_day должен быть от 0 (понедельник) до 6 (воскресенье)")
        return v
    
    @validator("weekly_report_hour")
    def validate_report_hour(cls, v: int) -> int:
        """Проверяем корректность часа"""
        if not 0 <= v <= 23:
            raise ValueError("weekly_report_hour должен быть от 0 до 23")
        return v
    
    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для Alembic"""
        if self.database_url:
            return self.database_url.replace("+asyncpg", "")
        return ""


# Создаем глобальный экземпляр настроек
settings = Settings()


def get_settings() -> Settings:
    """Получить настройки приложения"""
    return settings


# Дополнительные константы
class StatusCode:
    """HTTP статус коды для мониторинга"""
    OK = 200
    NOT_FOUND = 404
    SERVER_ERROR = 500
    TIMEOUT = 408
    UNKNOWN = 0


class SiteStatus:
    """Статусы сайтов"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"
    CHECKING = "checking"


class NotificationType:
    """Типы уведомлений"""
    SITE_DOWN = "site_down"
    SITE_UP = "site_up"
    WEEKLY_REPORT = "weekly_report"
    ERROR = "error"


# Настройки для разных окружений
def get_environment() -> str:
    """Определить текущее окружение"""
    return os.getenv("ENVIRONMENT", "production").lower()


def is_development() -> bool:
    """Проверить, работаем ли в режиме разработки"""
    return get_environment() == "development"


def is_production() -> bool:
    """Проверить, работаем ли в продакшне"""
    return get_environment() == "production"


# Конфигурация логирования
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": settings.log_format,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": settings.log_level,
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.log_level,
            "formatter": "detailed",
            "filename": "logs/bot.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "": {
            "level": settings.log_level,
            "handlers": ["console", "file"],
        },
        "aiogram": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "level": "WARNING",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}