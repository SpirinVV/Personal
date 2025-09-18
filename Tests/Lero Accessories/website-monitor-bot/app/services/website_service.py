"""
Сервис для работы с веб-сайтами.
"""

import logging
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Website, User, HealthCheck
from .user_service import UserService

logger = logging.getLogger(__name__)


class WebsiteService:
    """Сервис для работы с веб-сайтами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)
    
    async def add_website(
        self,
        owner_telegram_id: int,
        url: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        check_interval: int = 300,
        timeout: int = 10,
        max_retries: int = 3,
        monitor_content: bool = False
    ) -> Optional[Website]:
        """Добавить новый сайт для мониторинга"""
        try:
            # Получаем пользователя
            user = await self.user_service.get_user_by_telegram_id(owner_telegram_id)
            if not user:
                logger.error(f"Пользователь {owner_telegram_id} не найден")
                return None
            
            # Проверяем, не существует ли уже такой URL у пользователя
            existing_result = await self.session.execute(
                select(Website).where(
                    and_(
                        Website.owner_id == user.id,
                        Website.url == url
                    )
                )
            )
            existing_website = existing_result.scalar_one_or_none()
            
            if existing_website:
                logger.warning(f"Сайт {url} уже существует у пользователя {owner_telegram_id}")
                return existing_website
            
            # Создаем новый сайт
            website = Website(
                url=url,
                name=name,
                description=description,
                owner_id=user.id,
                check_interval=check_interval,
                timeout=timeout,
                max_retries=max_retries,
                monitor_content=monitor_content,
                is_active=True,
                current_status="unknown"
            )
            
            self.session.add(website)
            await self.session.commit()
            
            logger.info(f"Добавлен новый сайт {url} для пользователя {owner_telegram_id}")
            return website
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при добавлении сайта {url}: {e}")
            return None
    
    async def get_user_websites(
        self,
        telegram_id: int,
        active_only: bool = True
    ) -> List[Website]:
        """Получить все сайты пользователя"""
        try:
            # Оптимизированный запрос без дополнительного запроса пользователя
            query = (
                select(Website)
                .join(User, Website.owner_id == User.id)
                .where(User.telegram_id == telegram_id)
            )
            
            if active_only:
                query = query.where(Website.is_active == True)
            
            query = query.order_by(Website.created_at.desc())
            
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении сайтов пользователя {telegram_id}: {e}")
            return []
    
    async def get_website_details(self, website_id: int) -> Optional[Website]:
        """Получить детальную информацию о сайте"""
        try:
            result = await self.session.execute(
                select(Website)
                .options(selectinload(Website.owner))
                .where(Website.id == website_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Ошибка при получении деталей сайта {website_id}: {e}")
            return None
    
    async def update_website(
        self,
        website_id: int,
        owner_telegram_id: int,
        **update_data
    ) -> bool:
        """Обновить настройки сайта"""
        try:
            user = await self.user_service.get_user_by_telegram_id(owner_telegram_id)
            if not user:
                return False
            
            result = await self.session.execute(
                select(Website).where(
                    and_(
                        Website.id == website_id,
                        Website.owner_id == user.id
                    )
                )
            )
            website = result.scalar_one_or_none()
            
            if not website:
                return False
            
            # Обновляем поля
            for key, value in update_data.items():
                if hasattr(website, key):
                    setattr(website, key, value)
            
            await self.session.commit()
            logger.info(f"Обновлен сайт {website_id} пользователя {owner_telegram_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при обновлении сайта {website_id}: {e}")
            return False
    
    async def delete_website(
        self,
        website_id: int,
        owner_telegram_id: int
    ) -> bool:
        """Удалить сайт"""
        try:
            user = await self.user_service.get_user_by_telegram_id(owner_telegram_id)
            if not user:
                return False
            
            result = await self.session.execute(
                select(Website).where(
                    and_(
                        Website.id == website_id,
                        Website.owner_id == user.id
                    )
                )
            )
            website = result.scalar_one_or_none()
            
            if not website:
                return False
            
            await self.session.delete(website)
            await self.session.commit()
            
            logger.info(f"Удален сайт {website_id} пользователя {owner_telegram_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при удалении сайта {website_id}: {e}")
            return False
    
    async def toggle_website_status(
        self,
        website_id: int,
        owner_telegram_id: int
    ) -> bool:
        """Включить/отключить мониторинг сайта"""
        try:
            user = await self.user_service.get_user_by_telegram_id(owner_telegram_id)
            if not user:
                return False
            
            result = await self.session.execute(
                select(Website).where(
                    and_(
                        Website.id == website_id,
                        Website.owner_id == user.id
                    )
                )
            )
            website = result.scalar_one_or_none()
            
            if not website:
                return False
            
            website.is_active = not website.is_active
            await self.session.commit()
            
            status = "включен" if website.is_active else "отключен"
            logger.info(f"Мониторинг сайта {website_id} {status}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при изменении статуса сайта {website_id}: {e}")
            return False
    
    async def get_website_history(
        self,
        website_id: int,
        owner_telegram_id: int,
        limit: int = 50
    ) -> List[HealthCheck]:
        """Получить историю проверок сайта"""
        try:
            user = await self.user_service.get_user_by_telegram_id(owner_telegram_id)
            if not user:
                return []
            
            # Проверяем принадлежность сайта пользователю
            website_result = await self.session.execute(
                select(Website).where(
                    and_(
                        Website.id == website_id,
                        Website.owner_id == user.id
                    )
                )
            )
            website = website_result.scalar_one_or_none()
            
            if not website:
                return []
            
            # Получаем историю проверок
            result = await self.session.execute(
                select(HealthCheck)
                .where(HealthCheck.website_id == website_id)
                .order_by(HealthCheck.checked_at.desc())
                .limit(limit)
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении истории сайта {website_id}: {e}")
            return []
    
    async def get_all_active_websites(self) -> List[Website]:
        """Получить все активные сайты для мониторинга"""
        try:
            result = await self.session.execute(
                select(Website)
                .options(selectinload(Website.owner))
                .where(Website.is_active == True)
                .order_by(Website.id)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении всех активных сайтов: {e}")
            return []