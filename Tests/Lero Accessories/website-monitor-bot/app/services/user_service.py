"""
Сервис для работы с пользователями.
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import User, UserSettings, Website, HealthCheck

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_or_update_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> User:
        """Создать или обновить пользователя"""
        try:
            # Проверяем, существует ли пользователь
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем существующего пользователя
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.language_code = language_code or "en"
                user.is_active = True
            else:
                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code or "en",
                    is_active=True
                )
                self.session.add(user)
                await self.session.flush()  # Чтобы получить ID
                
                # Создаем настройки по умолчанию
                settings = UserSettings(user_id=user.id)
                self.session.add(settings)
            
            await self.session.commit()
            logger.info(f"Пользователь {telegram_id} создан/обновлен")
            return user
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при создании/обновлении пользователя {telegram_id}: {e}")
            raise
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        try:
            result = await self.session.execute(
                select(User)
                .options(selectinload(User.user_settings))
                .where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}")
            return None
    
    async def get_user_stats(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить статистику пользователя"""
        try:
            # Получаем пользователя
            user = await self.get_user_by_telegram_id(telegram_id)
            if not user:
                return None
            
            # Статистика по сайтам
            websites_result = await self.session.execute(
                select(
                    func.count(Website.id).label('total'),
                    func.count(Website.id).filter(Website.is_active == True).label('active'),
                    func.count(Website.id).filter(Website.current_status == 'up').label('up'),
                    func.count(Website.id).filter(Website.current_status == 'down').label('down')
                ).where(Website.owner_id == user.id)
            )
            website_stats = websites_result.first()
            
            # Статистика по проверкам
            checks_result = await self.session.execute(
                select(
                    func.count(HealthCheck.id).label('total_checks'),
                    func.count(HealthCheck.id).filter(HealthCheck.status == 'up').label('successful_checks'),
                    func.avg(HealthCheck.response_time).label('avg_response_time')
                )
                .select_from(HealthCheck)
                .join(Website)
                .where(Website.owner_id == user.id)
            )
            check_stats = checks_result.first()
            
            # Вычисляем средний uptime
            uptime_result = await self.session.execute(
                select(func.avg(Website.total_checks * 100.0 / func.nullif(Website.successful_checks, 0)))
                .where(Website.owner_id == user.id, Website.total_checks > 0)
            )
            avg_uptime = uptime_result.scalar() or 0.0
            
            return {
                'total_websites': website_stats.total or 0,
                'active_websites': website_stats.active or 0,
                'up_websites': website_stats.up or 0,
                'down_websites': website_stats.down or 0,
                'total_checks': check_stats.total_checks or 0,
                'successful_checks': check_stats.successful_checks or 0,
                'avg_response_time': check_stats.avg_response_time or 0.0,
                'avg_uptime': avg_uptime
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя {telegram_id}: {e}")
            return None
    
    async def update_user_settings(
        self,
        telegram_id: int,
        **settings_data
    ) -> bool:
        """Обновить настройки пользователя"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if not user:
                return False
            
            # Получаем или создаем настройки
            result = await self.session.execute(
                select(UserSettings).where(UserSettings.user_id == user.id)
            )
            user_settings = result.scalar_one_or_none()
            
            if not user_settings:
                user_settings = UserSettings(user_id=user.id)
                self.session.add(user_settings)
            
            # Обновляем настройки
            for key, value in settings_data.items():
                if hasattr(user_settings, key):
                    setattr(user_settings, key, value)
            
            await self.session.commit()
            logger.info(f"Настройки пользователя {telegram_id} обновлены")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при обновлении настроек пользователя {telegram_id}: {e}")
            return False
    
    async def is_admin(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        from ..config import settings
        
        # Проверяем в конфиге
        if telegram_id in settings.allowed_admins:
            return True
        
        # Проверяем в базе данных
        user = await self.get_user_by_telegram_id(telegram_id)
        return user.is_admin if user else False
    
    async def get_active_users(self) -> list[User]:
        """Получить всех активных пользователей"""
        try:
            result = await self.session.execute(
                select(User)
                .options(selectinload(User.user_settings))
                .where(User.is_active == True)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении активных пользователей: {e}")
            return []