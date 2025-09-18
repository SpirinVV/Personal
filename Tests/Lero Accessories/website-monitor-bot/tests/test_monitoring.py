"""
Тесты для сервиса мониторинга сайтов.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from app.services.monitor import MonitoringService
from app.models import Website
from app.config import SiteStatus


@pytest.fixture
def mock_bot():
    """Мок Telegram бота"""
    return MagicMock()


@pytest.fixture
def monitoring_service(mock_bot):
    """Фикстура сервиса мониторинга"""
    service = MonitoringService(mock_bot)
    service.session = AsyncMock()
    return service


@pytest.fixture
def sample_website():
    """Пример сайта для тестирования"""
    return Website(
        id=1,
        url="https://example.com",
        name="Test Site",
        owner_id=1,
        check_interval=300,
        timeout=10,
        is_active=True,
        current_status="unknown"
    )


@pytest_asyncio.async_test  
async def test_check_website_success(monitoring_service, sample_website):
    """Тест успешной проверки сайта"""
    # Настройка мока HTTP ответа
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.text.return_value = "test content"
    
    monitoring_service.session.get.return_value.__aenter__.return_value = mock_response
    
    # Выполняем проверку
    result = await monitoring_service.check_website(sample_website)
    
    # Проверяем результат
    assert result['status'] == SiteStatus.UP
    assert result['status_code'] == 200
    assert result['response_time'] is not None
    assert result['error_message'] is None


@pytest_asyncio.async_test
async def test_check_website_timeout(monitoring_service, sample_website):
    """Тест проверки сайта с таймаутом"""
    # Настройка мока для таймаута
    monitoring_service.session.get.side_effect = asyncio.TimeoutError()
    
    # Выполняем проверку
    result = await monitoring_service.check_website(sample_website)
    
    # Проверяем результат
    assert result['status'] == SiteStatus.DOWN
    assert result['error_message'] == 'Превышено время ожидания'
    assert result['response_time'] == sample_website.timeout * 1000


@pytest_asyncio.async_test  
async def test_check_website_client_error(monitoring_service, sample_website):
    """Тест проверки сайта с ошибкой клиента"""
    # Настройка мока для ошибки клиента
    monitoring_service.session.get.side_effect = aiohttp.ClientError("Connection failed")
    
    # Выполняем проверку
    result = await monitoring_service.check_website(sample_website)
    
    # Проверяем результат
    assert result['status'] == SiteStatus.DOWN
    assert "Connection failed" in result['error_message']


@pytest_asyncio.async_test
async def test_check_website_server_error(monitoring_service, sample_website):
    """Тест проверки сайта с ошибкой сервера"""
    # Настройка мока HTTP ответа с ошибкой
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.headers = {}
    
    monitoring_service.session.get.return_value.__aenter__.return_value = mock_response
    
    # Выполняем проверку
    result = await monitoring_service.check_website(sample_website)
    
    # Проверяем результат
    assert result['status'] == SiteStatus.DOWN
    assert result['status_code'] == 500