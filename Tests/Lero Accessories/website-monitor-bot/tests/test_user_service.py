"""
Тесты для сервиса пользователей.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.user_service import UserService
from app.models import User, UserSettings


@pytest.fixture
def mock_session():
    """Мок сессии базы данных"""
    session = AsyncMock()
    return session


@pytest.fixture  
def user_service(mock_session):
    """Фикстура сервиса пользователей"""
    return UserService(mock_session)


@pytest_asyncio.async_test
async def test_create_new_user(user_service, mock_session):
    """Тест создания нового пользователя"""
    # Настройка мока - пользователь не существует
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    
    # Создаем пользователя
    result = await user_service.create_or_update_user(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
        language_code="ru"
    )
    
    # Проверяем, что новый пользователь был добавлен
    mock_session.add.assert_called()
    mock_session.commit.assert_called()


@pytest_asyncio.async_test
async def test_update_existing_user(user_service, mock_session):
    """Тест обновления существующего пользователя"""
    # Настройка мока - пользователь существует
    existing_user = User(
        telegram_id=123456789,
        username="oldusername",
        first_name="Old",
        is_active=False
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing_user
    
    # Обновляем пользователя
    result = await user_service.create_or_update_user(
        telegram_id=123456789,
        username="newusername",
        first_name="New",
        last_name="User"
    )
    
    # Проверяем, что данные обновились
    assert existing_user.username == "newusername"
    assert existing_user.first_name == "New"
    assert existing_user.is_active == True
    mock_session.commit.assert_called()


@pytest_asyncio.async_test
async def test_get_user_by_telegram_id(user_service, mock_session):
    """Тест получения пользователя по Telegram ID"""
    # Настройка мока
    expected_user = User(telegram_id=123456789, username="testuser")
    mock_session.execute.return_value.scalar_one_or_none.return_value = expected_user
    
    # Получаем пользователя
    result = await user_service.get_user_by_telegram_id(123456789)
    
    # Проверяем результат
    assert result == expected_user


@pytest_asyncio.async_test
async def test_is_admin_from_config(user_service, mock_session):
    """Тест проверки админских прав из конфига"""
    from unittest.mock import patch
    
    with patch('app.services.user_service.settings') as mock_settings:
        mock_settings.allowed_admins = [123456789]
        
        # Проверяем администратора
        result = await user_service.is_admin(123456789)
        assert result == True
        
        # Проверяем обычного пользователя
        result = await user_service.is_admin(987654321)
        assert result == False