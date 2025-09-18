"""
Базовые обработчики команд бота.
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_db_session, User
from ..services.user_service import UserService
from ..config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async for session in get_db_session():
        user_service = UserService(session)
        
        # Создаем или обновляем пользователя
        user = await user_service.create_or_update_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        
        welcome_text = f"""
🔍 <b>Добро пожаловать в бот мониторинга сайтов!</b>

Привет, {message.from_user.first_name}! Я помогу вам отслеживать доступность ваших веб-сайтов.

<b>Что я умею:</b>
• 📊 Мониторить доступность сайтов 24/7
• ⚡ Мгновенно уведомлять об изменениях
• 📈 Предоставлять статистику и отчеты
• ⏱️ Измерять время отклика
• 🔧 Настраивать интервалы проверки

<b>Основные команды:</b>
/add - Добавить сайт для мониторинга
/list - Показать список отслеживаемых сайтов
/stats - Статистика по всем сайтам
/settings - Настройки уведомлений
/help - Справка по командам
        """
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="➕ Добавить сайт", callback_data="add_website"))
        keyboard.add(InlineKeyboardButton(text="📋 Мои сайты", callback_data="list_websites"))
        keyboard.add(InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"))
        keyboard.adjust(1)
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard.as_markup()
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📚 <b>Справка по командам</b>

<b>🌐 Управление сайтами:</b>
/add - Добавить новый сайт
/list - Список ваших сайтов
/remove - Удалить сайт
/edit - Редактировать настройки сайта

<b>📊 Статистика и отчеты:</b>
/stats - Общая статистика
/report - Детальный отчет
/history - История проверок

<b>⚙️ Настройки:</b>
/settings - Настройки уведомлений
/timezone - Установить временную зону
/interval - Настроить интервал проверки

<b>🔧 Дополнительно:</b>
/status - Проверить статус бота
/support - Техническая поддержка

❓ Для быстрого добавления сайта просто отправьте мне URL!
    """
    
    await message.answer(help_text)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработчик команды /stats"""
    async for session in get_db_session():
        user_service = UserService(session)
        stats = await user_service.get_user_stats(message.from_user.id)
        
        if not stats:
            await message.answer("📊 У вас пока нет отслеживаемых сайтов.")
            return
        
        stats_text = f"""
📊 <b>Ваша статистика</b>

🌐 <b>Всего сайтов:</b> {stats['total_websites']}
✅ <b>Активных:</b> {stats['active_websites']}
🟢 <b>Работающих:</b> {stats['up_websites']}
🔴 <b>Недоступных:</b> {stats['down_websites']}

📈 <b>Общий uptime:</b> {stats['avg_uptime']:.1f}%
⏱️ <b>Среднее время отклика:</b> {stats['avg_response_time']:.2f}с

🔍 <b>Всего проверок:</b> {stats['total_checks']}
✅ <b>Успешных:</b> {stats['successful_checks']}
        """
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="📋 Мои сайты", callback_data="list_websites"))
        keyboard.add(InlineKeyboardButton(text="📊 Детальный отчет", callback_data="detailed_report"))
        keyboard.adjust(1)
        
        await message.answer(
            stats_text,
            reply_markup=keyboard.as_markup()
        )


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Обработчик команды /settings"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications"))
    keyboard.add(InlineKeyboardButton(text="📅 Отчеты", callback_data="settings_reports"))
    keyboard.add(InlineKeyboardButton(text="🌍 Временная зона", callback_data="settings_timezone"))
    keyboard.add(InlineKeyboardButton(text="🔧 Дополнительно", callback_data="settings_advanced"))
    keyboard.adjust(2)
    
    await message.answer(
        "⚙️ <b>Настройки</b>\n\nВыберите категорию настроек:",
        reply_markup=keyboard.as_markup()
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Статус бота и системы"""
    from ..models import test_database_connection
    from ..services.monitor import MonitoringService
    
    # Проверяем подключение к БД
    db_status = "✅ Подключена" if await test_database_connection() else "❌ Недоступна"
    
    status_text = f"""
🤖 <b>Статус системы</b>

🗄️ <b>База данных:</b> {db_status}
🔍 <b>Мониторинг:</b> ✅ Активен
⚡ <b>Уведомления:</b> ✅ Работают

📊 <b>Версия:</b> 1.0.0
🆔 <b>Bot ID:</b> {message.bot.id}
    """
    
    await message.answer(status_text)


# URL Detection - автоматическое добавление сайтов
@router.message(F.text.regexp(r'https?://[^\s]+'))
async def auto_add_website(message: Message):
    """Автоматическое добавление сайта по URL"""
    url = message.text.strip()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="➕ Добавить для мониторинга", 
        callback_data=f"quick_add:{url}"
    ))
    keyboard.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
    keyboard.adjust(1)
    
    await message.answer(
        f"🔗 Обнаружен URL: <code>{url}</code>\n\n"
        f"Хотите добавить этот сайт для мониторинга?",
        reply_markup=keyboard.as_markup()
    )


def register_basic_handlers(dp) -> None:
    """Регистрация базовых обработчиков"""
    dp.include_router(router)