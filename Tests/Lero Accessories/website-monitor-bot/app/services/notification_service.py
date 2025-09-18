"""
Сервис уведомлений для отправки сообщений пользователям.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..config import NotificationType
from ..models import get_db_session, User, Website, Incident, Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений пользователям"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def send_site_down_notification(
        self, 
        website: Website, 
        incident: Incident, 
        check_result: Dict[str, Any]
    ) -> None:
        """Отправка уведомления о падении сайта"""
        try:
            async for db_session in get_db_session():
                # Получаем владельца сайта
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                
                result = await db_session.execute(
                    select(User)
                    .options(selectinload(User.user_settings))
                    .where(User.id == website.owner_id)
                )
                owner = result.scalar_one_or_none()
                
                if not owner or not owner.notification_enabled:
                    return
                
                # Проверяем настройки уведомлений
                if owner.user_settings and not owner.user_settings.notify_on_down:
                    return
                
                # Формируем сообщение
                message = self._format_site_down_message(website, incident, check_result)
                
                # Отправляем уведомление
                await self._send_notification(
                    db_session,
                    owner,
                    NotificationType.SITE_DOWN,
                    "🔴 Сайт недоступен",
                    message,
                    website_id=website.id,
                    incident_id=incident.id
                )
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о падении сайта: {e}")
    
    async def send_site_recovery_notification(
        self, 
        website: Website, 
        incident: Incident, 
        check_result: Dict[str, Any]
    ) -> None:
        """Отправка уведомления о восстановлении сайта"""
        try:
            async for db_session in get_db_session():
                # Получаем владельца сайта
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                
                result = await db_session.execute(
                    select(User)
                    .options(selectinload(User.user_settings))
                    .where(User.id == website.owner_id)
                )
                owner = result.scalar_one_or_none()
                
                if not owner or not owner.notification_enabled:
                    return
                
                # Проверяем настройки уведомлений
                if owner.user_settings and not owner.user_settings.notify_on_up:
                    return
                
                # Формируем сообщение
                message = self._format_site_recovery_message(website, incident, check_result)
                
                # Отправляем уведомление
                await self._send_notification(
                    db_session,
                    owner,
                    NotificationType.SITE_UP,
                    "✅ Сайт восстановлен",
                    message,
                    website_id=website.id,
                    incident_id=incident.id
                )
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о восстановлении сайта: {e}")
    
    async def send_weekly_report(self, user: User) -> None:
        """Отправка еженедельного отчета"""
        try:
            async for db_session in get_db_session():
                # Генерируем отчет
                report = await self._generate_weekly_report(db_session, user)
                
                if not report:
                    return
                
                # Отправляем отчет
                await self._send_notification(
                    db_session,
                    user,
                    NotificationType.WEEKLY_REPORT,
                    "📊 Еженедельный отчет",
                    report
                )
                
        except Exception as e:
            logger.error(f"Ошибка при отправке еженедельного отчета: {e}")
    
    def _format_site_down_message(
        self, 
        website: Website, 
        incident: Incident, 
        check_result: Dict[str, Any]
    ) -> str:
        """Форматирование сообщения о падении сайта"""
        site_name = website.name or website.url
        status_code = check_result.get('status_code', 'N/A')
        error_message = check_result.get('error_message', 'Неизвестная ошибка')
        
        message = f"""
🔴 <b>Сайт недоступен!</b>

🌐 <b>Сайт:</b> {site_name}
🔗 <b>URL:</b> <code>{website.url}</code>
📅 <b>Время:</b> {incident.started_at.strftime('%d.%m.%Y %H:%M:%S')}

❌ <b>Статус код:</b> {status_code}
⚠️ <b>Ошибка:</b> {error_message}

🔍 Я продолжаю мониторинг и уведомлю о восстановлении.
        """
        
        return message.strip()
    
    def _format_site_recovery_message(
        self, 
        website: Website, 
        incident: Incident, 
        check_result: Dict[str, Any]
    ) -> str:
        """Форматирование сообщения о восстановлении сайта"""
        site_name = website.name or website.url
        duration_minutes = incident.duration_minutes or 0
        response_time = check_result.get('response_time', 0)
        
        message = f"""
✅ <b>Сайт восстановлен!</b>

🌐 <b>Сайт:</b> {site_name}
🔗 <b>URL:</b> <code>{website.url}</code>
📅 <b>Восстановлен:</b> {incident.resolved_at.strftime('%d.%m.%Y %H:%M:%S')}

⏱️ <b>Время недоступности:</b> {duration_minutes} мин.
🚀 <b>Время отклика:</b> {response_time:.2f} мс

🎉 Ваш сайт снова работает!
        """
        
        return message.strip()
    
    async def _generate_weekly_report(self, db_session, user: User) -> Optional[str]:
        """Генерация еженедельного отчета"""
        try:
            from sqlalchemy import select, func
            from datetime import timedelta
            
            # Период отчета (последние 7 дней)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Получаем статистику
            websites_result = await db_session.execute(
                select(
                    func.count(Website.id).label('total_websites'),
                    func.count(Website.id).filter(Website.current_status == 'up').label('up_websites'),
                    func.avg(Website.last_response_time).label('avg_response_time')
                ).where(Website.owner_id == user.id, Website.is_active == True)
            )
            website_stats = websites_result.first()
            
            if not website_stats.total_websites:
                return None
            
            # Статистика по инцидентам
            incidents_result = await db_session.execute(
                select(
                    func.count(Incident.id).label('total_incidents'),
                    func.avg(Incident.duration).label('avg_duration')
                )
                .select_from(Incident)
                .join(Website)
                .where(
                    Website.owner_id == user.id,
                    Incident.started_at >= start_date,
                    Incident.started_at <= end_date
                )
            )
            incident_stats = incidents_result.first()
            
            # Формируем отчет
            uptime_percentage = (website_stats.up_websites / website_stats.total_websites) * 100
            avg_response = website_stats.avg_response_time or 0
            total_incidents = incident_stats.total_incidents or 0
            avg_downtime = (incident_stats.avg_duration or 0) / 60  # в минутах
            
            report = f"""
📊 <b>Еженедельный отчет</b>
<i>Период: {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}</i>

🌐 <b>Сайтов под мониторингом:</b> {website_stats.total_websites}
🟢 <b>Доступных сейчас:</b> {website_stats.up_websites}
📈 <b>Общий uptime:</b> {uptime_percentage:.1f}%

⏱️ <b>Среднее время отклика:</b> {avg_response:.2f} мс
🚨 <b>Инцидентов за неделю:</b> {total_incidents}

{"❌ <b>Среднее время простоя:</b> " + f"{avg_downtime:.1f} мин." if total_incidents > 0 else "🎉 <b>Все сайты работали стабильно!</b>"}

Продолжаю мониторинг ваших сайтов 24/7! 🔍
            """
            
            return report.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации еженедельного отчета: {e}")
            return None
    
    async def _send_notification(
        self,
        db_session,
        user: User,
        notification_type: str,
        title: str,
        message: str,
        website_id: Optional[int] = None,
        incident_id: Optional[int] = None
    ) -> None:
        """Отправка уведомления пользователю"""
        try:
            # Создаем запись уведомления
            notification = Notification(
                user_id=user.id,
                website_id=website_id,
                incident_id=incident_id,
                notification_type=notification_type,
                title=title,
                message=message
            )
            
            db_session.add(notification)
            await db_session.flush()
            
            # Отправляем сообщение
            try:
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='HTML'
                )
                
                # Помечаем как отправленное
                notification.sent = True
                notification.delivered = True
                notification.sent_at = datetime.now()
                
            except Exception as send_error:
                # Логируем ошибку отправки
                notification.sent = False
                notification.error_message = str(send_error)
                logger.error(f"Ошибка отправки сообщения пользователю {user.telegram_id}: {send_error}")
            
            await db_session.commit()
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при сохранении уведомления: {e}")