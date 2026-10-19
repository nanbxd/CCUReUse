from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import ForeignKey, String, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database.models import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(60), default='Встреча')
    capacity: Mapped[int]
    target_budget: Mapped[int] = mapped_column(default=0)
    ticket_price: Mapped[int] = mapped_column(default=0)
    min_tickets_required: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default='exploration', index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    estimate: Mapped[str] = mapped_column(Text, default='')
    kaspi_details: Mapped[str] = mapped_column(String(300), default='')
    deadline_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Ticket(Base):
    __tablename__ = 'tickets'
    __table_args__ = (UniqueConstraint('event_id', 'user_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey('events.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    kaspi_transaction_screenshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_completed: Mapped[bool] = mapped_column(Boolean, default=False)

class Review(Base):
    __tablename__ = 'reviews'
    __table_args__ = (UniqueConstraint('event_id', 'user_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey('events.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    rating: Mapped[int]
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class EventInterest(Base):
    __tablename__ = 'event_interests'
    event_id: Mapped[str] = mapped_column(ForeignKey('events.id'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)

class EventNotification(Base):
    __tablename__ = 'event_notifications'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey('events.id'))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
