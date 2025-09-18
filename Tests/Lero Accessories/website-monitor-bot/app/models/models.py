"""
Модели базы данных для системы мониторинга сайтов.
Используется SQLAlchemy с асинхронным драйвером asyncpg.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, 
    ForeignKey, Float, JSON, Index, CheckConstraint
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """Модель пользователя Telegram бота"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    # Настройки пользователя
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekly_reports: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Связи
    websites: Mapped[List["Website"]] = relationship(
        "Website", 
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    user_settings: Mapped[Optional["UserSettings"]] = relationship(
        "UserSettings", 
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"


class UserSettings(Base):
    """Настройки пользователя"""
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Настройки уведомлений
    notify_on_down: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_up: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_slow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slow_threshold: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)  # секунды
    
    # Настройки отчетов
    daily_summary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Временная зона пользователя
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="user_settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id})>"


class Website(Base):
    """Модель отслеживаемого сайта"""
    __tablename__ = "websites"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Владелец сайта
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Настройки мониторинга
    check_interval: Mapped[int] = mapped_column(Integer, default=300, nullable=False)  # секунды
    timeout: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # секунды
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    
    # Состояние
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Мониторинг содержимого (опционально)
    monitor_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Статистика
    total_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    # Связи
    owner: Mapped["User"] = relationship("User", back_populates="websites")
    checks: Mapped[List["HealthCheck"]] = relationship(
        "HealthCheck", 
        back_populates="website",
        cascade="all, delete-orphan"
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident", 
        back_populates="website",
        cascade="all, delete-orphan"
    )
    
    # Индексы
    __table_args__ = (
        Index("idx_website_owner_active", "owner_id", "is_active"),
        Index("idx_website_status", "current_status"),
        Index("idx_website_last_check", "last_check"),
        CheckConstraint("check_interval > 0", name="positive_check_interval"),
        CheckConstraint("timeout > 0", name="positive_timeout"),
        CheckConstraint("max_retries >= 0", name="non_negative_retries"),
    )
    
    @property
    def uptime_percentage(self) -> float:
        """Вычисляет процент uptime"""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100
    
    def __repr__(self) -> str:
        return f"<Website(id={self.id}, url='{self.url}', status='{self.current_status}')>"


class HealthCheck(Base):
    """Модель результата проверки сайта"""
    __tablename__ = "health_checks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    website_id: Mapped[int] = mapped_column(Integer, ForeignKey("websites.id"), nullable=False)
    
    # Результаты проверки
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # up, down, timeout, error
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # миллисекунды
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Дополнительная информация
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # SSL информация
    ssl_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ssl_issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    
    # Связи
    website: Mapped["Website"] = relationship("Website", back_populates="checks")
    
    # Индексы
    __table_args__ = (
        Index("idx_health_check_website_date", "website_id", "checked_at"),
        Index("idx_health_check_status", "status"),
        Index("idx_health_check_date", "checked_at"),
    )
    
    def __repr__(self) -> str:
        return f"<HealthCheck(id={self.id}, website_id={self.website_id}, status='{self.status}')>"


class Incident(Base):
    """Модель инцидента (периода недоступности)"""
    __tablename__ = "incidents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    website_id: Mapped[int] = mapped_column(Integer, ForeignKey("websites.id"), nullable=False)
    
    # Информация об инциденте
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="minor", nullable=False)  # minor, major, critical
    
    # Временные рамки
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # секунды
    
    # Статус инцидента
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open, resolved, investigating
    
    # Уведомления
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    # Связи
    website: Mapped["Website"] = relationship("Website", back_populates="incidents")
    
    # Индексы
    __table_args__ = (
        Index("idx_incident_website", "website_id"),
        Index("idx_incident_status", "status"),
        Index("idx_incident_started", "started_at"),
        Index("idx_incident_severity", "severity"),
    )
    
    @property
    def is_resolved(self) -> bool:
        """Проверяет, разрешен ли инцидент"""
        return self.resolved_at is not None
    
    @property
    def duration_minutes(self) -> Optional[int]:
        """Возвращает длительность в минутах"""
        if self.duration:
            return self.duration // 60
        return None
    
    def __repr__(self) -> str:
        return f"<Incident(id={self.id}, website_id={self.website_id}, status='{self.status}')>"


class Notification(Base):
    """Модель отправленных уведомлений"""
    __tablename__ = "notifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    website_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("websites.id"), nullable=True)
    incident_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("incidents.id"), nullable=True)
    
    # Тип и содержание уведомления
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Статус доставки
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Метаданные
    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Индексы
    __table_args__ = (
        Index("idx_notification_user", "user_id"),
        Index("idx_notification_type", "notification_type"),
        Index("idx_notification_sent", "sent"),
        Index("idx_notification_created", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type='{self.notification_type}', sent={self.sent})>"