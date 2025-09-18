"""
Тесты для конфигурации приложения.
"""

import pytest
from app.config import Settings


def test_settings_creation():
    """Тест создания настроек с базовыми значениями"""
    settings = Settings(
        bot_token="test_token",
        db_password="test_password"
    )
    
    assert settings.bot_token == "test_token"
    assert settings.db_password == "test_password"
    assert settings.default_check_interval == 300
    assert settings.request_timeout == 10


def test_database_url_assembly():
    """Тест сборки URL базы данных"""
    settings = Settings(
        bot_token="test_token",
        db_password="test_password",
        db_host="localhost",
        db_port=5432,
        db_name="test_db",
        db_user="test_user"
    )
    
    expected_url = "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"
    assert settings.database_url == expected_url


def test_admin_ids_parsing():
    """Тест парсинга ID администраторов"""
    settings = Settings(
        bot_token="test_token",
        db_password="test_password",
        allowed_admins="123,456,789"
    )
    
    assert settings.allowed_admins == [123, 456, 789]


def test_empty_admin_ids():
    """Тест пустого списка администраторов"""
    settings = Settings(
        bot_token="test_token",
        db_password="test_password",
        allowed_admins=""
    )
    
    assert settings.allowed_admins == []


def test_invalid_admin_ids():
    """Тест некорректных ID администраторов"""
    settings = Settings(
        bot_token="test_token",
        db_password="test_password",
        allowed_admins="123,abc,456"
    )
    
    assert settings.allowed_admins == [123, 456]