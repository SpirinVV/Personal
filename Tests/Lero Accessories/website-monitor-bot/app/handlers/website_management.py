import logging
import validators
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..models import get_db_session
from ..services.user_service import UserService
from ..services.website_service import WebsiteService

logger = logging.getLogger(__name__)
router = Router()


class AddWebsiteStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_name = State()
    waiting_for_interval = State()


@router.message(Command("add"))
async def cmd_add_website(message: Message, state: FSMContext):
    await state.set_state(AddWebsiteStates.waiting_for_url)
    await message.answer(
        "🌐 <b>Добавление нового сайта</b>\n\n"
        "Введите URL сайта для мониторинга:\n"
        "(например: https://example.com)"
    )


@router.message(AddWebsiteStates.waiting_for_url)
async def process_website_url(message: Message, state: FSMContext):
    url = message.text.strip()
    
    if not validators.url(url):
        await message.answer(
            "❌ Некорректный URL. Пожалуйста, введите правильный адрес:\n"
            "(например: https://example.com)"
        )
        return
    
    await state.update_data(url=url)
    await state.set_state(AddWebsiteStates.waiting_for_name)
    
    await message.answer(
        f"✅ URL принят: <code>{url}</code>\n\n"
        "📝 Введите название сайта (или отправьте /skip для пропуска):"
    )


@router.message(AddWebsiteStates.waiting_for_name)
async def process_website_name(message: Message, state: FSMContext):
    if message.text.strip() == "/skip":
        name = None
    else:
        name = message.text.strip()
    
    await state.update_data(name=name)
    await state.set_state(AddWebsiteStates.waiting_for_interval)
    
    await message.answer(
        "⏱️ Установите интервал проверки (в секундах):\n\n"
        "• 60 - каждую минуту\n"
        "• 300 - каждые 5 минут (рекомендуется)\n"
        "• 600 - каждые 10 минут\n"
        "• 1800 - каждые 30 минут\n\n"
        "Или отправьте /skip для значения по умолчанию (300 сек)"
    )


@router.message(AddWebsiteStates.waiting_for_interval)
async def process_website_interval(message: Message, state: FSMContext):
    if message.text.strip() == "/skip":
        interval = 300
    else:
        try:
            interval = int(message.text.strip())
            if interval < 60:
                await message.answer("❌ Минимальный интервал - 60 секунд")
                return
            if interval > 3600:
                await message.answer("❌ Максимальный интервал - 3600 секунд (1 час)")
                return
        except ValueError:
            await message.answer("❌ Введите число от 60 до 3600")
            return
    
    data = await state.get_data()
    url = data['url']
    name = data.get('name')
    
    async for session in get_db_session():
        website_service = WebsiteService(session)
        
        website = await website_service.add_website(
            owner_telegram_id=message.from_user.id,
            url=url,
            name=name,
            check_interval=interval
        )
        
        if website:
            from ..main import bot_instance
            if bot_instance.monitoring_service:
                await bot_instance.monitoring_service.start_monitoring_website(website.id)
            
            await message.answer(
                f"✅ <b>Сайт добавлен!</b>\n\n"
                f"🌐 <b>URL:</b> <code>{url}</code>\n"
                f"📝 <b>Название:</b> {name or 'Не указано'}\n"
                f"⏱️ <b>Интервал:</b> {interval} сек\n\n"
                f"🔍 Мониторинг запущен!"
            )
        else:
            await message.answer("❌ Ошибка при добавлении сайта. Попробуйте позже.")
    
    await state.clear()


@router.message(Command("list"))
async def cmd_list_websites(message: Message):
    async for session in get_db_session():
        website_service = WebsiteService(session)
        websites = await website_service.get_user_websites(message.from_user.id)
        
        if not websites:
            await message.answer(
                "📋 У вас пока нет сайтов для мониторинга.\n"
                "Используйте /add для добавления первого сайта."
            )
            return
        
        keyboard = InlineKeyboardBuilder()
        
        text = "📋 <b>Ваши сайты:</b>\n\n"
        
        for i, website in enumerate(websites, 1):
            status_emoji = "🟢" if website.current_status == "up" else "🔴" if website.current_status == "down" else "⚪"
            name = website.name or website.url[:30] + "..."
            
            text += f"{status_emoji} <b>{i}. {name}</b>\n"
            text += f"   🔗 <code>{website.url}</code>\n"
            
            if website.last_check:
                text += f"   🔍 Последняя проверка: {website.last_check.strftime('%d.%m %H:%M')}\n"
            
            if website.last_response_time:
                text += f"   ⚡ Время отклика: {website.last_response_time:.0f}мс\n"
            
            text += f"   📊 Uptime: {website.uptime_percentage:.1f}%\n\n"
            
            keyboard.add(InlineKeyboardButton(
                text=f"📊 {name[:15]}...",
                callback_data=f"website_details:{website.id}"
            ))
        
        keyboard.add(InlineKeyboardButton(text="➕ Добавить сайт", callback_data="add_website"))
        keyboard.adjust(2, 1)
        
        await message.answer(text, reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("website_details:"))
async def show_website_details(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    async for session in get_db_session():
        website_service = WebsiteService(session)
        website = await website_service.get_website_details(website_id)
        
        if not website:
            await callback.answer("❌ Сайт не найден")
            return
        
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        if not user or website.owner_id != user.id:
            await callback.answer("❌ Нет доступа к этому сайту")
            return
        
        status_emoji = "🟢" if website.current_status == "up" else "🔴" if website.current_status == "down" else "⚪"
        name = website.name or "Без названия"
        
        text = f"""
{status_emoji} <b>{name}</b>

🔗 <b>URL:</b> <code>{website.url}</code>
📊 <b>Статус:</b> {website.current_status.upper()}
⏱️ <b>Интервал проверки:</b> {website.check_interval} сек

📈 <b>Статистика:</b>
• Uptime: {website.uptime_percentage:.1f}%
• Всего проверок: {website.total_checks}
• Успешных: {website.successful_checks}
        """
        
        if website.last_check:
            text += f"\n🔍 <b>Последняя проверка:</b> {website.last_check.strftime('%d.%m.%Y %H:%M:%S')}"
        
        if website.last_response_time:
            text += f"\n⚡ <b>Время отклика:</b> {website.last_response_time:.0f} мс"
        
        if website.last_error:
            text += f"\n❌ <b>Последняя ошибка:</b> {website.last_error}"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🔄 Проверить сейчас", callback_data=f"check_now:{website.id}"))
        keyboard.add(InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"website_settings:{website.id}"))
        keyboard.add(InlineKeyboardButton(text="📊 История", callback_data=f"website_history:{website.id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_website:{website.id}"))
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="list_websites"))
        keyboard.adjust(2, 2, 1)
        
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("check_now:"))
async def force_check_website(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    await callback.answer("🔍 Выполняю проверку...")
    
    from ..main import bot_instance
    if bot_instance.monitoring_service:
        result = await bot_instance.monitoring_service.force_check_website(website_id)
        
        if result:
            status = "✅ Доступен" if result['status'] == 'up' else "❌ Недоступен"
            response_time = f"{result['response_time']:.0f} мс" if result['response_time'] else "N/A"
            
            await callback.message.answer(
                f"🔍 <b>Результат проверки:</b>\n\n"
                f"📊 <b>Статус:</b> {status}\n"
                f"⚡ <b>Время отклика:</b> {response_time}\n"
                f"🔢 <b>HTTP код:</b> {result.get('status_code', 'N/A')}"
            )
        else:
            await callback.message.answer("❌ Ошибка при выполнении проверки")


@router.callback_query(F.data.startswith("delete_website:"))
async def confirm_delete_website(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{website_id}"))
    keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"website_details:{website_id}"))
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        "Вы уверены, что хотите удалить этот сайт?\n"
        "Вся история мониторинга будет потеряна.",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_website(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    async for session in get_db_session():
        website_service = WebsiteService(session)
        success = await website_service.delete_website(website_id, callback.from_user.id)
        
        if success:
            from ..main import bot_instance
            if bot_instance.monitoring_service:
                await bot_instance.monitoring_service.stop_monitoring_website(website_id)
            
            await callback.message.edit_text("✅ Сайт успешно удален")
        else:
            await callback.message.edit_text("❌ Ошибка при удалении сайта")


@router.callback_query(F.data == "add_website")
async def callback_add_website(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Получен callback add_website от пользователя {callback.from_user.id}")
    
    await state.set_state(AddWebsiteStates.waiting_for_url)
    await callback.message.answer(
        "🌐 <b>Добавление нового сайта</b>\n\n"
        "Введите URL сайта для мониторинга:\n"
        "(например: https://example.com)"
    )
    await callback.answer()
    logger.info("Callback add_website обработан успешно")


@router.callback_query(F.data == "list_websites")
async def callback_list_websites(callback: CallbackQuery):
    logger.info(f"Получен callback list_websites от пользователя {callback.from_user.id}")
    
    await callback.answer()
    
    loading_msg = await callback.message.answer("🔄 Загружаю список сайтов...")
    
    try:
        async for session in get_db_session():
            website_service = WebsiteService(session)
            websites = await website_service.get_user_websites(callback.from_user.id)
            
            if not websites:
                await loading_msg.edit_text(
                    "📋 У вас пока нет сайтов для мониторинга.\n"
                    "Используйте /add для добавления первого сайта."
                )
                return
            
            keyboard = InlineKeyboardBuilder()
            
            text = "📋 <b>Ваши сайты:</b>\n\n"
            
            for i, website in enumerate(websites, 1):
                status_emoji = "🟢" if website.current_status == "up" else "🔴" if website.current_status == "down" else "⚪"
                
                text += f"{status_emoji} {i}. <b>{website.name}</b>\n"
                text += f"   🔗 {website.url}\n"
                text += f"   📊 Uptime: {website.uptime_percentage:.1f}%\n"
                
                if website.last_check:
                    if website.current_status == "up":
                        text += f"   ✅ Последняя проверка: {website.last_check.strftime('%d.%m.%Y %H:%M')}\n"
                        if website.last_response_time:
                            text += f"   ⏱️ Время отклика: {website.last_response_time:.0f}ms\n"
                    else:
                        text += f"   ❌ Недоступен с: {website.last_check.strftime('%d.%m.%Y %H:%M')}\n"
                else:
                    text += "   ⏳ Еще не проверялся\n"
                
                text += "\n"
                
                keyboard.row(
                    InlineKeyboardButton(
                        text=f"📊 {website.name}",
                        callback_data=f"website_details:{website.id}"
                    ),
                    InlineKeyboardButton(
                        text="🔄 Проверить",
                        callback_data=f"check_now:{website.id}"
                    )
                )
            
            keyboard.row(
                InlineKeyboardButton(text="➕ Добавить сайт", callback_data="add_website"),
                InlineKeyboardButton(text="📈 Общая статистика", callback_data="general_stats")
            )
            
            await loading_msg.edit_text(text, reply_markup=keyboard.as_markup())
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка сайтов: {e}")
        await loading_msg.edit_text("❌ Произошла ошибка при загрузке списка сайтов")
    
    logger.info("Callback list_websites обработан успешно")


@router.callback_query(F.data.startswith("quick_add:"))
async def callback_quick_add(callback: CallbackQuery, state: FSMContext):
    url = callback.data.split(":", 1)[1]
    logger.info(f"Быстрое добавление сайта {url} от пользователя {callback.from_user.id}")
    
    if not validators.url(url):
        await callback.answer("❌ Некорректный URL", show_alert=True)
        return
    
    await state.update_data(url=url)
    await state.set_state(AddWebsiteStates.waiting_for_name)
    
    await callback.message.edit_text(
        f"✅ URL принят: {url}\n\n"
        "📝 Теперь введите название сайта:\n"
        "(например: Мой блог, Интернет-магазин и т.д.)"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Операция отменена")
    await callback.answer()


@router.callback_query(F.data == "general_stats")
async def callback_general_stats(callback: CallbackQuery):
    await callback.answer("📈 Общая статистика находится в разработке...")


@router.callback_query(F.data.startswith("website_history:"))
async def callback_website_history(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    async for session in get_db_session():
        website_service = WebsiteService(session)
        website = await website_service.get_website_details(website_id)
        
        if not website:
            await callback.answer("❌ Сайт не найден")
            return
        
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        if not user or website.owner_id != user.id:
            await callback.answer("❌ Нет доступа к этому сайту")
            return
        
        text = f"""
📊 <b>История проверок: {website.name or 'Без названия'}</b>

🔗 <b>URL:</b> <code>{website.url}</code>

📈 <b>Общая статистика:</b>
• Всего проверок: {website.total_checks}
• Успешных: {website.successful_checks}
• Uptime: {website.uptime_percentage:.1f}%

⏱️ <b>Интервал проверки:</b> {website.check_interval} сек
"""
        
        if website.last_check:
            text += f"\n🔍 <b>Последняя проверка:</b> {website.last_check.strftime('%d.%m.%Y %H:%M:%S')}"
        
        if website.last_response_time:
            text += f"\n⚡ <b>Время отклика:</b> {website.last_response_time:.0f} мс"
        
        if website.last_error:
            text += f"\n❌ <b>Последняя ошибка:</b> {website.last_error}"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"website_details:{website_id}"))
        
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    
    await callback.answer()


@router.callback_query(F.data.startswith("website_settings:"))
async def callback_website_settings(callback: CallbackQuery):
    website_id = int(callback.data.split(":")[1])
    
    async for session in get_db_session():
        website_service = WebsiteService(session)
        website = await website_service.get_website_details(website_id)
        
        if not website:
            await callback.answer("❌ Сайт не найден")
            return
        
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        if not user or website.owner_id != user.id:
            await callback.answer("❌ Нет доступа к этому сайту")
            return
        
        text = f"""
⚙️ <b>Настройки: {website.name or 'Без названия'}</b>

🔗 <b>URL:</b> <code>{website.url}</code>
📝 <b>Название:</b> {website.name or 'Не указано'}
⏱️ <b>Интервал проверки:</b> {website.check_interval} сек
📊 <b>Текущий статус:</b> {website.current_status.upper()}

<i>Функции редактирования находятся в разработке</i>
"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"website_details:{website_id}"))
        
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    
    await callback.answer()


@router.callback_query()
async def catch_all_callbacks(callback: CallbackQuery):
    logger.warning(f"Необработанный callback: {callback.data} от пользователя {callback.from_user.id}")
    await callback.answer("Функция в разработке...")


def register_website_handlers(dp) -> None:
    dp.include_router(router)