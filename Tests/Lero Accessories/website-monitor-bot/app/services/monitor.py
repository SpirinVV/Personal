import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
import aiohttp
import hashlib
from urllib.parse import urlparse

from ..config import settings, SiteStatus
from ..models import get_db_session, Website, HealthCheck, Incident, User
from .notification_service import NotificationService

logger = logging.getLogger(__name__)


class MonitoringService:
    def __init__(self, bot):
        self.bot = bot
        self.notification_service = NotificationService(bot)
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self) -> None:
        if self.is_running:
            return
        
        logger.info("Запуск сервиса мониторинга...")
        self.is_running = True
        
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        await self._start_monitoring_all_websites()
        
        logger.info("Сервис мониторинга запущен")
    
    async def stop(self) -> None:
        if not self.is_running:
            return
        
        logger.info("Остановка сервиса мониторинга...")
        self.is_running = False
        
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        if self.session:
            await self.session.close()
        
        self.monitoring_tasks.clear()
        logger.info("Сервис мониторинга остановлен")
    
    async def _start_monitoring_all_websites(self) -> None:
        async for db_session in get_db_session():
            try:
                from sqlalchemy import select
                result = await db_session.execute(
                    select(Website).where(Website.is_active == True)
                )
                websites = result.scalars().all()
                
                for website in websites:
                    await self.start_monitoring_website(website.id)
                    
            except Exception as e:
                logger.error(f"Ошибка при запуске мониторинга всех сайтов: {e}")
    
    async def start_monitoring_website(self, website_id: int) -> None:
        if website_id in self.monitoring_tasks:
            self.monitoring_tasks[website_id].cancel()
        
        task = asyncio.create_task(self._monitor_website_loop(website_id))
        self.monitoring_tasks[website_id] = task
        
        logger.info(f"Запущен мониторинг сайта ID {website_id}")
    
    async def stop_monitoring_website(self, website_id: int) -> None:
        if website_id in self.monitoring_tasks:
            self.monitoring_tasks[website_id].cancel()
            del self.monitoring_tasks[website_id]
            logger.info(f"Остановлен мониторинг сайта ID {website_id}")
    
    async def _monitor_website_loop(self, website_id: int) -> None:
        while self.is_running:
            try:
                async for db_session in get_db_session():
                    result = await db_session.execute(
                        select(Website).where(Website.id == website_id)
                    )
                    website = result.scalar_one_or_none()
                    
                    if not website or not website.is_active:
                        break
                    
                    check_result = await self._check_website(website)
                    
                    await self._save_health_check(db_session, website, check_result)
                    
                    await self._handle_status_change(db_session, website, check_result)
                    
                    await asyncio.sleep(website.check_interval)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка при мониторинге сайта {website_id}: {e}")
                await asyncio.sleep(60)
    
    async def _check_website(self, website: Website) -> Dict[str, Any]:
        start_time = time.time()
        result = {
            'status': SiteStatus.DOWN,
            'status_code': None,
            'response_time': None,
            'error': None,
            'content_length': None,
            'content_hash': None
        }
        
        try:
            async with self.session.get(website.url) as response:
                response_time = (time.time() - start_time) * 1000
                
                result['status_code'] = response.status
                result['response_time'] = response_time
                
                if 200 <= response.status < 300:
                    result['status'] = SiteStatus.UP
                    
                    content = await response.read()
                    result['content_length'] = len(content)
                    result['content_hash'] = hashlib.md5(content).hexdigest()
                else:
                    result['error'] = f"HTTP {response.status}"
                    
        except asyncio.TimeoutError:
            result['error'] = "Timeout"
        except aiohttp.ClientError as e:
            result['error'] = str(e)
        except Exception as e:
            result['error'] = f"Unexpected error: {e}"
        
        return result
    
    async def _save_health_check(self, db_session, website: Website, check_result: Dict[str, Any]) -> None:
        try:
            health_check = HealthCheck(
                website_id=website.id,
                status=check_result['status'],
                status_code=check_result['status_code'],
                response_time=check_result['response_time'],
                error_message=check_result['error'],
                content_length=check_result['content_length'],
                content_hash=check_result['content_hash'],
                checked_at=datetime.now()
            )
            
            db_session.add(health_check)
            
            website.last_check = datetime.now()
            website.last_response_time = check_result['response_time']
            website.last_error = check_result['error']
            
            await db_session.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении результата проверки: {e}")
            await db_session.rollback()
    
    async def _handle_status_change(self, db_session, website: Website, check_result: Dict[str, Any]) -> None:
        old_status = website.current_status
        new_status = check_result['status']
        
        if old_status != new_status:
            logger.info(f"Изменение статуса сайта {website.url}: {old_status} -> {new_status}")
            
            website.current_status = new_status
            
            if old_status == SiteStatus.UP and new_status == SiteStatus.DOWN:
                await self._handle_site_down(db_session, website, check_result)
            elif old_status == SiteStatus.DOWN and new_status == SiteStatus.UP:
                await self._handle_site_up(db_session, website)
            
            await db_session.commit()
    
    async def _handle_site_down(self, db_session, website: Website, check_result: Dict[str, Any]) -> None:
        try:
            incident = Incident(
                website_id=website.id,
                status='open',
                started_at=datetime.now(),
                error_message=check_result['error']
            )
            
            db_session.add(incident)
            await db_session.flush()
            
            await self.notification_service.send_downtime_notification(website, incident)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке недоступности сайта: {e}")
    
    async def _handle_site_up(self, db_session, website: Website) -> None:
        try:
            from sqlalchemy import select, update
            
            result = await db_session.execute(
                select(Incident)
                .where(Incident.website_id == website.id)
                .where(Incident.status == 'open')
                .order_by(Incident.started_at.desc())
            )
            incident = result.scalar_one_or_none()
            
            if incident:
                incident.status = 'resolved'
                incident.resolved_at = datetime.now()
                
                await self.notification_service.send_recovery_notification(website, incident)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке восстановления сайта: {e}")
    
    async def force_check_website(self, website_id: int) -> Optional[Dict[str, Any]]:
        try:
            async for db_session in get_db_session():
                from sqlalchemy import select
                result = await db_session.execute(
                    select(Website).where(Website.id == website_id)
                )
                website = result.scalar_one_or_none()
                
                if not website:
                    return None
                
                check_result = await self._check_website(website)
                
                await self._save_health_check(db_session, website, check_result)
                await self._handle_status_change(db_session, website, check_result)
                
                return check_result
                
        except Exception as e:
            logger.error(f"Ошибка при принудительной проверке сайта {website_id}: {e}")
            return None