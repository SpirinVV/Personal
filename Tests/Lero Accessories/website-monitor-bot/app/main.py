"""
Основной файл приложения - точка входа для Telegram бота.
"""

import asyncio
import logging
import logging.config
import os
import signal
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import settings, LOGGING_CONFIG
from .models import init_database, close_database, test_database_connection
from .handlers import register_handlers
from .services.monitor import MonitoringService
from .utils.logger_setup import setup_logging


# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class WebsiteMonitorBot:
    """Главный класс Telegram бота для мониторинга сайтов"""
    
    def __init__(self):
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.monitoring_service: MonitoringService = None
        self._shutdown = False
    
    async def init_bot(self) -> None:
        """Инициализация бота"""
        try:
            # Создаем бота
            self.bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Создаем диспетчер
            self.dp = Dispatcher(storage=MemoryStorage())
            
            # Регистрируем хендлеры
            register_handlers(self.dp)
            
            # Инициализируем базу данных
            await init_database()
            
            # Проверяем подключение к БД
            if not await test_database_connection():
                raise RuntimeError("Не удалось подключиться к базе данных")
            
            # Инициализируем сервис мониторинга
            self.monitoring_service = MonitoringService(self.bot)
            
            logger.info("Бот успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            raise
    
    async def start_polling(self) -> None:
        """Запуск polling режима"""
        try:
            logger.info("Запуск бота в режиме polling...")
            
            # Запускаем сервис мониторинга
            await self.monitoring_service.start()
            
            # Получаем информацию о боте
            bot_info = await self.bot.get_me()
            logger.info(f"Бот @{bot_info.username} успешно запущен!")
            
            # Запускаем polling
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            logger.error(f"Ошибка во время polling: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Корректное завершение работы бота"""
        if self._shutdown:
            return
            
        self._shutdown = True
        logger.info("Завершение работы бота...")
        
        try:
            # Останавливаем сервис мониторинга
            if self.monitoring_service:
                await self.monitoring_service.stop()
            
            # Закрываем сессию бота
            if self.bot:
                await self.bot.session.close()
            
            # Закрываем соединение с БД
            await close_database()
            
            logger.info("Бот успешно завершил работу")
            
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")


# Глобальный экземпляр бота
bot_instance = WebsiteMonitorBot()


async def main() -> None:
    """Главная функция"""
    try:
        # Создаем директорию для логов
        os.makedirs("logs", exist_ok=True)
        
        # Инициализируем и запускаем бота
        await bot_instance.init_bot()
        await bot_instance.start_polling()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        await bot_instance.shutdown()


def handle_signal(signum, frame):
    """Обработчик системных сигналов"""
    logger.info(f"Получен сигнал {signum}")
    # Создаем task для корректного завершения
    asyncio.create_task(bot_instance.shutdown())


if __name__ == "__main__":
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Запускаем приложение
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение завершено пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        sys.exit(1)