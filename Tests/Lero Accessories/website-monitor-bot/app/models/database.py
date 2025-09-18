"""
Инициализация базы данных и создание сессий.
"""

import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    async_sessionmaker, 
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from ..config import settings
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: AsyncEngine = None
        self.session_factory: async_sessionmaker[AsyncSession] = None
        
    def create_engine(self) -> AsyncEngine:
        """Создает движок базы данных"""
        return create_async_engine(
            self.database_url,
            echo=False,  # Устанавливаем в True для отладки SQL запросов
            poolclass=NullPool,  # Для контейнеров лучше использовать NullPool
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    
    async def init_db(self) -> None:
        """Инициализация базы данных"""
        try:
            self.engine = self.create_engine()
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Создаем таблицы (в продакшене используйте Alembic)
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
            logger.info("База данных успешно инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    async def close(self) -> None:
        """Закрытие соединения с базой данных"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Соединение с базой данных закрыто")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Получить сессию базы данных"""
        if not self.session_factory:
            raise RuntimeError("База данных не инициализирована")
            
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager(settings.database_url or "")


async def init_database() -> None:
    """Инициализация базы данных"""
    await db_manager.init_db()


async def close_database() -> None:
    """Закрытие базы данных"""
    await db_manager.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии базы данных"""
    async for session in db_manager.get_session():
        yield session


async def test_database_connection() -> bool:
    """Проверка соединения с базой данных"""
    try:
        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        return False
    return False