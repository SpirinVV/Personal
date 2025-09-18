import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..models import get_db_session, User, Website
from ..services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()


async def is_admin_filter(message_or_callback):
    user_id = message_or_callback.from_user.id
    
    async for session in get_db_session():
        user_service = UserService(session)
        return await user_service.is_admin(user_id)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin_filter(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Статистика системы", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton(text="🌐 Все сайты", callback_data="admin_websites"))
    keyboard.add(InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs"))
    keyboard.add(InlineKeyboardButton(text="🔄 Перезапуск мониторинга", callback_data="admin_restart_monitoring"))
    keyboard.adjust(1)
    
    await message.answer(
        "🔧 <b>Административная панель</b>\n\n"
        "Выберите нужное действие:",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_system_stats(callback: CallbackQuery):
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select, func
            from ..models import User, Website, HealthCheck, Incident
            
            users_result = await session.execute(
                select(
                    func.count(User.id).label('total_users'),
                    func.count(User.id).filter(User.is_active == True).label('active_users'),
                    func.count(User.id).filter(User.is_admin == True).label('admin_users')
                )
            )
            user_stats = users_result.first()
            
            websites_result = await session.execute(
                select(
                    func.count(Website.id).label('total_websites'),
                    func.count(Website.id).filter(Website.is_active == True).label('active_websites'),
                    func.count(Website.id).filter(Website.current_status == 'up').label('up_websites'),
                    func.count(Website.id).filter(Website.current_status == 'down').label('down_websites')
                )
            )
            website_stats = websites_result.first()
            
            from datetime import datetime, timedelta
            yesterday = datetime.now() - timedelta(days=1)
            
            checks_result = await session.execute(
                select(
                    func.count(HealthCheck.id).label('total_checks'),
                    func.count(HealthCheck.id).filter(HealthCheck.status == 'up').label('successful_checks')
                ).where(HealthCheck.checked_at >= yesterday)
            )
            check_stats = checks_result.first()
            
            week_ago = datetime.now() - timedelta(days=7)
            incidents_result = await session.execute(
                select(
                    func.count(Incident.id).label('total_incidents'),
                    func.count(Incident.id).filter(Incident.status == 'open').label('open_incidents')
                ).where(Incident.started_at >= week_ago)
            )
            incident_stats = incidents_result.first()
            
            success_rate = (check_stats.successful_checks / check_stats.total_checks * 100) if check_stats.total_checks > 0 else 0
            
            stats_text = f"""
📊 <b>Статистика системы</b>

👥 <b>Пользователи:</b>
• Всего: {user_stats.total_users}
• Активных: {user_stats.active_users}  
• Администраторов: {user_stats.admin_users}

🌐 <b>Сайты:</b>
• Всего: {website_stats.total_websites}
• Активных: {website_stats.active_websites}
• Работающих: {website_stats.up_websites}
• Недоступных: {website_stats.down_websites}

🔍 <b>Проверки (24ч):</b>
• Всего: {check_stats.total_checks}
• Успешных: {check_stats.successful_checks}
• Успешность: {success_rate:.1f}%

🚨 <b>Инциденты (7 дней):</b>
• Всего: {incident_stats.total_incidents}
• Открытых: {incident_stats.open_incidents}
            """
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats"))
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            keyboard.adjust(1)
            
            await callback.message.edit_text(
                stats_text.strip(),
                reply_markup=keyboard.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await callback.message.edit_text("❌ Ошибка при получении статистики")


@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select
            
            result = await session.execute(
                select(User)
                .order_by(User.created_at.desc())
                .limit(20)
            )
            users = result.scalars().all()
            
            if not users:
                await callback.message.edit_text("👥 Пользователи не найдены")
                return
            
            text = "👥 <b>Последние пользователи:</b>\n\n"
            
            for user in users:
                status = "🟢" if user.is_active else "🔴"
                admin_mark = "👑" if user.is_admin else ""
                username = f"@{user.username}" if user.username else "Без username"
                
                text += f"{status} {admin_mark} <b>{user.first_name or 'Без имени'}</b>\n"
                text += f"   {username} (ID: {user.telegram_id})\n"
                text += f"   Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            
            await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            await callback.message.edit_text("❌ Ошибка при получении списка пользователей")


@router.callback_query(F.data == "admin_websites")
async def admin_websites_list(callback: CallbackQuery):
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
            result = await session.execute(
                select(Website)
                .options(selectinload(Website.owner))
                .order_by(Website.created_at.desc())
                .limit(15)
            )
            websites = result.scalars().all()
            
            if not websites:
                await callback.message.edit_text("🌐 Сайты не найдены")
                return
            
            text = "🌐 <b>Все сайты:</b>\n\n"
            
            for website in websites:
                status_emoji = "🟢" if website.current_status == "up" else "🔴" if website.current_status == "down" else "⚪"
                active_mark = "✅" if website.is_active else "⏸️"
                owner_name = website.owner.first_name if website.owner else "Unknown"
                
                text += f"{status_emoji} {active_mark} <b>{website.name or 'Без названия'}</b>\n"
                text += f"   🔗 <code>{website.url[:50]}...</code>\n"
                text += f"   👤 Владелец: {owner_name}\n"
                text += f"   📊 Uptime: {website.uptime_percentage:.1f}%\n\n"
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            
            await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка сайтов: {e}")
            await callback.message.edit_text("❌ Ошибка при получении списка сайтов")


@router.callback_query(F.data == "admin_restart_monitoring")
async def admin_restart_monitoring(callback: CallbackQuery):
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    try:
        from ..main import bot_instance
        
        if bot_instance.monitoring_service:
            await bot_instance.monitoring_service.stop()
            await bot_instance.monitoring_service.start()
        
        await callback.message.edit_text("✅ Мониторинг перезапущен")
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске мониторинга: {e}")
        await callback.message.edit_text("❌ Ошибка при перезапуске мониторинга")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await cmd_admin(callback.message)
    await callback.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not await is_admin_filter(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    text = message.text.replace("/broadcast", "").strip()
    
    if not text:
        await message.answer(
            "📢 <b>Рассылка сообщений</b>\n\n"
            "Использование: <code>/broadcast текст сообщения</code>\n\n"
            "Сообщение будет отправлено всем активным пользователям."
        )
        return
    
    async for session in get_db_session():
        try:
            user_service = UserService(session)
            users = await user_service.get_active_users()
            
            sent_count = 0
            failed_count = 0
            
            status_message = await message.answer("📤 Начинаю рассылку...")
            
            for user in users:
                try:
                    await message.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                        parse_mode='HTML'
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
            
            await status_message.edit_text(
                f"✅ <b>Рассылка завершена</b>\n\n"
                f"📤 Отправлено: {sent_count}\n"
                f"❌ Ошибок: {failed_count}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке: {e}")
            await message.answer("❌ Ошибка при выполнении рассылки")


def register_admin_handlers(dp) -> None:
    dp.include_router(router)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Административная панель"""
    if not await is_admin_filter(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Статистика системы", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton(text="🌐 Все сайты", callback_data="admin_websites"))
    keyboard.add(InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs"))
    keyboard.add(InlineKeyboardButton(text="🔄 Перезапуск мониторинга", callback_data="admin_restart_monitoring"))
    keyboard.adjust(1)
    
    await message.answer(
        "🔧 <b>Административная панель</b>\n\n"
        "Выберите нужное действие:",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_system_stats(callback: CallbackQuery):
    """Статистика системы"""
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select, func
            from ..models import User, Website, HealthCheck, Incident
            
            # Статистика пользователей
            users_result = await session.execute(
                select(
                    func.count(User.id).label('total_users'),
                    func.count(User.id).filter(User.is_active == True).label('active_users'),
                    func.count(User.id).filter(User.is_admin == True).label('admin_users')
                )
            )
            user_stats = users_result.first()
            
            # Статистика сайтов
            websites_result = await session.execute(
                select(
                    func.count(Website.id).label('total_websites'),
                    func.count(Website.id).filter(Website.is_active == True).label('active_websites'),
                    func.count(Website.id).filter(Website.current_status == 'up').label('up_websites'),
                    func.count(Website.id).filter(Website.current_status == 'down').label('down_websites')
                )
            )
            website_stats = websites_result.first()
            
            # Статистика проверок (за последние 24 часа)
            from datetime import datetime, timedelta
            yesterday = datetime.now() - timedelta(days=1)
            
            checks_result = await session.execute(
                select(
                    func.count(HealthCheck.id).label('total_checks'),
                    func.count(HealthCheck.id).filter(HealthCheck.status == 'up').label('successful_checks')
                ).where(HealthCheck.checked_at >= yesterday)
            )
            check_stats = checks_result.first()
            
            # Статистика инцидентов (за последние 7 дней)
            week_ago = datetime.now() - timedelta(days=7)
            incidents_result = await session.execute(
                select(
                    func.count(Incident.id).label('total_incidents'),
                    func.count(Incident.id).filter(Incident.status == 'open').label('open_incidents')
                ).where(Incident.started_at >= week_ago)
            )
            incident_stats = incidents_result.first()
            
            # Формируем отчет
            success_rate = (check_stats.successful_checks / check_stats.total_checks * 100) if check_stats.total_checks > 0 else 0
            
            stats_text = f"""
📊 <b>Статистика системы</b>

👥 <b>Пользователи:</b>
• Всего: {user_stats.total_users}
• Активных: {user_stats.active_users}  
• Администраторов: {user_stats.admin_users}

🌐 <b>Сайты:</b>
• Всего: {website_stats.total_websites}
• Активных: {website_stats.active_websites}
• Работающих: {website_stats.up_websites}
• Недоступных: {website_stats.down_websites}

🔍 <b>Проверки (24ч):</b>
• Всего: {check_stats.total_checks}
• Успешных: {check_stats.successful_checks}
• Успешность: {success_rate:.1f}%

🚨 <b>Инциденты (7 дней):</b>
• Всего: {incident_stats.total_incidents}
• Открытых: {incident_stats.open_incidents}
            """
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats"))
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            keyboard.adjust(1)
            
            await callback.message.edit_text(
                stats_text.strip(),
                reply_markup=keyboard.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await callback.message.edit_text("❌ Ошибка при получении статистики")


@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    """Список пользователей"""
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select
            
            result = await session.execute(
                select(User)
                .order_by(User.created_at.desc())
                .limit(20)
            )
            users = result.scalars().all()
            
            if not users:
                await callback.message.edit_text("👥 Пользователи не найдены")
                return
            
            text = "👥 <b>Последние пользователи:</b>\n\n"
            
            for user in users:
                status = "🟢" if user.is_active else "🔴"
                admin_mark = "👑" if user.is_admin else ""
                username = f"@{user.username}" if user.username else "Без username"
                
                text += f"{status} {admin_mark} <b>{user.first_name or 'Без имени'}</b>\n"
                text += f"   {username} (ID: {user.telegram_id})\n"
                text += f"   Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            
            await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            await callback.message.edit_text("❌ Ошибка при получении списка пользователей")


@router.callback_query(F.data == "admin_websites")
async def admin_websites_list(callback: CallbackQuery):
    """Список всех сайтов"""
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    async for session in get_db_session():
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
            result = await session.execute(
                select(Website)
                .options(selectinload(Website.owner))
                .order_by(Website.created_at.desc())
                .limit(15)
            )
            websites = result.scalars().all()
            
            if not websites:
                await callback.message.edit_text("🌐 Сайты не найдены")
                return
            
            text = "🌐 <b>Все сайты:</b>\n\n"
            
            for website in websites:
                status_emoji = "🟢" if website.current_status == "up" else "🔴" if website.current_status == "down" else "⚪"
                active_mark = "✅" if website.is_active else "⏸️"
                owner_name = website.owner.first_name if website.owner else "Unknown"
                
                text += f"{status_emoji} {active_mark} <b>{website.name or 'Без названия'}</b>\n"
                text += f"   🔗 <code>{website.url[:50]}...</code>\n"
                text += f"   👤 Владелец: {owner_name}\n"
                text += f"   📊 Uptime: {website.uptime_percentage:.1f}%\n\n"
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
            
            await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка сайтов: {e}")
            await callback.message.edit_text("❌ Ошибка при получении списка сайтов")


@router.callback_query(F.data == "admin_restart_monitoring")
async def admin_restart_monitoring(callback: CallbackQuery):
    """Перезапуск мониторинга"""
    if not await is_admin_filter(callback):
        await callback.answer("❌ Нет прав доступа")
        return
    
    try:
        from ..main import bot_instance
        
        # Останавливаем и запускаем мониторинг
        if bot_instance.monitoring_service:
            await bot_instance.monitoring_service.stop()
            await bot_instance.monitoring_service.start()
        
        await callback.message.edit_text("✅ Мониторинг перезапущен")
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске мониторинга: {e}")
        await callback.message.edit_text("❌ Ошибка при перезапуске мониторинга")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """Возврат в админ панель"""
    await cmd_admin(callback.message)
    await callback.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Рассылка сообщения всем пользователям"""
    if not await is_admin_filter(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Получаем текст для рассылки (все после команды)
    text = message.text.replace("/broadcast", "").strip()
    
    if not text:
        await message.answer(
            "📢 <b>Рассылка сообщений</b>\n\n"
            "Использование: <code>/broadcast текст сообщения</code>\n\n"
            "Сообщение будет отправлено всем активным пользователям."
        )
        return
    
    async for session in get_db_session():
        try:
            user_service = UserService(session)
            users = await user_service.get_active_users()
            
            sent_count = 0
            failed_count = 0
            
            status_message = await message.answer("📤 Начинаю рассылку...")
            
            for user in users:
                try:
                    await message.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                        parse_mode='HTML'
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
            
            await status_message.edit_text(
                f"✅ <b>Рассылка завершена</b>\n\n"
                f"📤 Отправлено: {sent_count}\n"
                f"❌ Ошибок: {failed_count}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке: {e}")
            await message.answer("❌ Ошибка при выполнении рассылки")


def register_admin_handlers(dp) -> None:
    """Регистрация административных обработчиков"""
    dp.include_router(router)