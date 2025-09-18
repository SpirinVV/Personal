"""
Сервис мониторинга сайтов.
"""

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
    """Сервис мониторинга веб-сайтов"""
    
    def __init__(self, bot):
        self.bot = bot
        self.notification_service = NotificationService(bot)
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self) -> None:
        """Запуск сервиса мониторинга"""
        if self.is_running:
            return
        
        logger.info("Запуск сервиса мониторинга...")
        self.is_running = True
        
        # Создаем HTTP сессию
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Запускаем мониторинг для всех активных сайтов
        await self._start_monitoring_all_websites()
        
        logger.info("Сервис мониторинга запущен")
    
    async def stop(self) -> None:
        """Остановка сервиса мониторинга"""
        if not self.is_running:
            return
        
        logger.info("Остановка сервиса мониторинга...")
        self.is_running = False
        
        # Останавливаем все задачи мониторинга
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # Ждем завершения задач
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        # Закрываем HTTP сессию
        if self.session:
            await self.session.close()
        
        self.monitoring_tasks.clear()
        logger.info("Сервис мониторинга остановлен")
    
    async def _start_monitoring_all_websites(self) -> None:
        """Запуск мониторинга для всех активных сайтов"""
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
        """Запуск мониторинга конкретного сайта"""
        if website_id in self.monitoring_tasks:
            # Останавливаем существующую задачу
            self.monitoring_tasks[website_id].cancel()
        
        # Создаем новую задачу мониторинга
        task = asyncio.create_task(self._monitor_website_loop(website_id))
        self.monitoring_tasks[website_id] = task
        
        logger.info(f"Запущен мониторинг сайта ID {website_id}")
    
    async def stop_monitoring_website(self, website_id: int) -> None:
        """Остановка мониторинга конкретного сайта"""
        if website_id in self.monitoring_tasks:
            self.monitoring_tasks[website_id].cancel()
            del self.monitoring_tasks[website_id]
            logger.info(f"Остановлен мониторинг сайта ID {website_id}")
    
    async def _monitor_website_loop(self, website_id: int) -> None:
        """Цикл мониторинга одного сайта"""
        while self.is_running:
            try:
                async for db_session in get_db_session():
                    # Получаем актуальную информацию о сайте
                    from sqlalchemy import select
                    result = await db_session.execute(
                        select(Website).where(Website.id == website_id)
                    )
                    website = result.scalar_one_or_none()
                    
                    if not website or not website.is_active:
                        break
                    
                    # Выполняем проверку
                    check_result = await self.check_website(website)
                    
                    # Сохраняем результат в БД
                    await self._save_check_result(db_session, website, check_result)
                    
                    # Обрабатываем изменение статуса
                    await self._handle_status_change(db_session, website, check_result)
                    
                    # Ждем до следующей проверки
                    await asyncio.sleep(website.check_interval)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга сайта {website_id}: {e}")
                await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой
    
    async def check_website(self, website: Website) -> Dict[str, Any]:
        """Проверка доступности сайта"""
        start_time = time.time()
        
        check_result = {
            'website_id': website.id,
            'status': SiteStatus.UNKNOWN,
            'status_code': None,
            'response_time': None,
            'error_message': None,
            'headers': None,
            'content_length': None,
            'content_hash': None,
            'ssl_expiry': None,
            'ssl_issuer': None
        }
        
        try:
            async with self.session.get(
                website.url,
                timeout=aiohttp.ClientTimeout(total=website.timeout)
            ) as response:
                response_time = (time.time() - start_time) * 1000  # в миллисекундах
                
                check_result.update({
                    'status': SiteStatus.UP if response.status < 400 else SiteStatus.DOWN,
                    'status_code': response.status,
                    'response_time': response_time,
                    'headers': dict(response.headers),
                    'content_length': int(response.headers.get('content-length', 0)) if response.headers.get('content-length') else None
                })
                
                # Читаем содержимое для мониторинга изменений
                if website.monitor_content:
                    content = await response.text()
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    check_result['content_hash'] = content_hash
                
                # Проверяем SSL сертификат для HTTPS
                if website.url.startswith('https'):
                    # Здесь можно добавить проверку SSL сертификата
                    pass
                
        except asyncio.TimeoutError:
            check_result.update({
                'status': SiteStatus.DOWN,
                'error_message': 'Превышено время ожидания',
                'response_time': website.timeout * 1000
            })
        except aiohttp.ClientError as e:
            check_result.update({
                'status': SiteStatus.DOWN,
                'error_message': str(e)
            })
        except Exception as e:
            check_result.update({
                'status': SiteStatus.DOWN,
                'error_message': f'Неизвестная ошибка: {str(e)}'
            })
        
        return check_result
    
    async def _save_check_result(
        self, 
        db_session, 
        website: Website, 
        check_result: Dict[str, Any]
    ) -> None:
        """Сохранение результата проверки в БД"""
        try:
            # Создаем запись о проверке
            health_check = HealthCheck(
                website_id=website.id,
                status=check_result['status'],
                status_code=check_result['status_code'],
                response_time=check_result['response_time'],
                error_message=check_result['error_message'],
                headers=check_result['headers'],
                content_length=check_result['content_length'],
                content_hash=check_result['content_hash'],
                ssl_expiry=check_result['ssl_expiry'],
                ssl_issuer=check_result['ssl_issuer']
            )
            
            db_session.add(health_check)
            
            # Обновляем статистику сайта
            website.last_check = datetime.now()
            website.last_response_time = check_result['response_time']
            website.last_status_code = check_result['status_code']
            website.last_error = check_result['error_message']
            website.total_checks += 1
            
            if check_result['status'] == SiteStatus.UP:
                website.successful_checks += 1
            
            # Обновляем хэш содержимого если нужно
            if check_result['content_hash']:
                website.content_hash = check_result['content_hash']
            
            await db_session.commit()
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при сохранении результата проверки: {e}")
    
    async def _handle_status_change(
        self, 
        db_session, 
        website: Website, 
        check_result: Dict[str, Any]
    ) -> None:
        """Обработка изменения статуса сайта"""
        new_status = check_result['status']
        previous_status = website.current_status
        
        # Обновляем текущий статус
        website.current_status = new_status
        
        # Если статус изменился
        if previous_status != new_status:
            logger.info(f"Изменение статуса сайта {website.url}: {previous_status} -> {new_status}")
            
            if new_status == SiteStatus.DOWN and previous_status == SiteStatus.UP:
                # Сайт упал
                await self._handle_site_down(db_session, website, check_result)
            elif new_status == SiteStatus.UP and previous_status == SiteStatus.DOWN:
                # Сайт восстановился
                await self._handle_site_recovery(db_session, website, check_result)
    
    async def _handle_site_down(
        self, 
        db_session, 
        website: Website, 
        check_result: Dict[str, Any]
    ) -> None:
        """Обработка падения сайта"""
        try:
            # Создаем инцидент
            incident = Incident(
                website_id=website.id,
                title=f"Сайт {website.name or website.url} недоступен",
                description=check_result.get('error_message', 'Причина неизвестна'),
                severity='major' if check_result.get('status_code', 0) >= 500 else 'minor',
                started_at=datetime.now(),
                status='open'
            )
            
            db_session.add(incident)
            await db_session.flush()
            
            # Отправляем уведомление
            await self.notification_service.send_site_down_notification(
                website, incident, check_result
            )
            
            incident.notification_sent = True
            await db_session.commit()
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при обработке падения сайта: {e}")
    
    async def _handle_site_recovery(
        self, 
        db_session, 
        website: Website, 
        check_result: Dict[str, Any]
    ) -> None:
        """Обработка восстановления сайта"""
        try:
            # Закрываем открытые инциденты
            from sqlalchemy import select, update
            
            open_incidents_result = await db_session.execute(
                select(Incident).where(
                    Incident.website_id == website.id,
                    Incident.status == 'open'
                )
            )
            open_incidents = open_incidents_result.scalars().all()
            
            for incident in open_incidents:
                incident.resolved_at = datetime.now()
                incident.status = 'resolved'
                incident.duration = int((incident.resolved_at - incident.started_at).total_seconds())
                
                # Отправляем уведомление о восстановлении
                if not incident.resolution_notification_sent:
                    await self.notification_service.send_site_recovery_notification(
                        website, incident, check_result
                    )
                    incident.resolution_notification_sent = True
            
            await db_session.commit()
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при обработке восстановления сайта: {e}")
    
    async def force_check_website(self, website_id: int) -> Optional[Dict[str, Any]]:
        """Принудительная проверка сайта"""
        async for db_session in get_db_session():
            try:
                from sqlalchemy import select
                result = await db_session.execute(
                    select(Website).where(Website.id == website_id)
                )
                website = result.scalar_one_or_none()
                
                if not website:
                    return None
                
                # Выполняем проверку
                check_result = await self.check_website(website)
                
                # Сохраняем результат
                await self._save_check_result(db_session, website, check_result)
                
                return check_result
                
            except Exception as e:
                logger.error(f"Ошибка при принудительной проверке сайта {website_id}: {e}")
                return None