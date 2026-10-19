from datetime import datetime, timezone
import base64, hashlib, hmac, math
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator, field_validator
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from .database.db import get_db, SessionLocal
from .database.models import User
from .event_models import Event, Ticket, Review, EventInterest, EventNotification, now
from config import settings

def utc(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def fail(message, code=400): raise HTTPException(code, message)

def settle(db):
    for event in db.scalars(select(Event).where(Event.status.in_(['crowdfunding', 'confirmed'])).with_for_update()).all():
        if event.status == 'crowdfunding' and utc(event.deadline_date) <= now():
            paid = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.event_id == event.id, Ticket.status == 'paid'))
            next_status = 'confirmed' if paid >= event.min_tickets_required else 'cancelled'
            claimed = db.execute(update(Event).where(Event.id == event.id, Event.status == 'crowdfunding').values(status=next_status))
            if claimed.rowcount != 1:
                continue
            event.status = next_status
            for ticket in db.scalars(select(Ticket).where(Ticket.event_id == event.id)).all():
                if event.status == 'cancelled' and ticket.status == 'paid':
                    ticket.status = 'refunded'
                    ticket.updated_at = now()
                db.add(EventNotification(user_id=ticket.user_id, event_id=event.id, message=f'«{event.title}»: ' + ('мероприятие подтверждено. Билет активен.' if event.status == 'confirmed' else 'мероприятие отменено. Если вы переводили деньги, свяжитесь с организатором для возврата.')))
        if event.status == 'confirmed' and utc(event.end_date or event.event_date) <= now(): event.status = 'completed'
    db.commit()

async def lifecycle():
    import asyncio, logging
    while True:
        try:
            with SessionLocal() as db: settle(db)
        except Exception: logging.getLogger(__name__).exception('Event lifecycle failed')
        await asyncio.sleep(30)

class EventIn(BaseModel):
    model_config = {'str_strip_whitespace': True}
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=5000)
    location: str = Field(min_length=2, max_length=300)
    category: Literal['Встреча', 'Спорт', 'Творчество', 'Образование', 'Вечеринка', 'Конференция', 'Концерт', 'Фестиваль'] = 'Встреча'
    capacity: int = Field(ge=1, le=100000)
    target_budget: int = Field(default=0, ge=0, le=100000000)
    ticket_price: int = Field(default=0, ge=0, le=1000000)
    is_private: bool = True
    deadline_date: datetime
    event_date: datetime
    end_date: datetime | None = None
    banner: str = Field(default='', max_length=2_800_000)

    @field_validator('banner')
    @classmethod
    def valid_banner(cls, value):
        if not value:
            return value
        try:
            mime, encoded = value.split(',', 1)
            if mime not in ('data:image/jpeg;base64', 'data:image/png;base64', 'data:image/webp;base64'):
                raise ValueError()
            image = base64.b64decode(encoded, validate=True)
            signatures = (image.startswith(b'\x89PNG\r\n\x1a\n'), image.startswith(b'\xff\xd8\xff'), image[:4] == b'RIFF' and image[8:12] == b'WEBP')
            if not any(signatures) or len(image) > 2_000_000:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Баннер должен быть изображением JPEG, PNG или WebP до 2 МБ')
        return value
    @model_validator(mode='after')
    def dates(self):
        if not now() < utc(self.deadline_date) < utc(self.event_date): raise ValueError('Срок сбора должен быть в будущем и раньше мероприятия')
        if self.end_date and utc(self.end_date) <= utc(self.event_date): raise ValueError('Окончание должно быть позже начала мероприятия')
        if bool(self.ticket_price) != bool(self.target_budget): raise ValueError('Укажите и бюджет, и цену либо оставьте оба нулевыми')
        if self.ticket_price and math.ceil(self.target_budget / self.ticket_price) > self.capacity: raise ValueError('Вместимости недостаточно для сбора бюджета')
        return self

class LaunchIn(BaseModel):
    estimate: str = Field(default='', max_length=5000)
    kaspi_details: str = Field(default='', max_length=300)
class BookingIn(BaseModel):
    screenshot: str = Field(default='', max_length=2800000)
class VerifyIn(BaseModel):
    qr_code_hash: str = Field(min_length=64, max_length=64)
class ReviewIn(BaseModel):
    model_config = {'str_strip_whitespace': True}
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=2000)
class RoleIn(BaseModel):
    is_organizer: bool

def router_for(current_user):
    router = APIRouter(prefix='/api')
    def get_event(db, event_id, lock=False):
        stmt = select(Event).where(Event.id == event_id)
        event = db.scalar(stmt.with_for_update() if lock else stmt)
        if not event: fail('Мероприятие не найдено', 404)
        return event
    def owner(event, user):
        if event.creator_id != user.id and not user.is_admin: fail('Доступ только организатору мероприятия', 403)
    def event_data(db, event):
        creator = db.get(User, event.creator_id)
        counts = dict(db.execute(select(Ticket.status, func.count()).where(Ticket.event_id == event.id).group_by(Ticket.status)).all())
        return {**{c.name: utc(getattr(event, c.name)) if isinstance(getattr(event, c.name), datetime) else getattr(event, c.name) for c in Event.__table__.columns if c.name != 'kaspi_details'}, 'creator': {'id': creator.id, 'name': creator.name}, 'paid_count': counts.get('paid', 0) + counts.get('used', 0), 'reserved_count': sum(counts.get(s, 0) for s in ('pending', 'paid', 'used')), 'interest_count': db.scalar(select(func.count()).select_from(EventInterest).where(EventInterest.event_id == event.id))}
    def ticket_data(db, ticket):
        event = get_event(db, ticket.event_id)
        return {'id': ticket.id, 'status': ticket.status, 'updated_at': utc(ticket.updated_at), 'used_at': utc(ticket.used_at) if ticket.used_at else None, 'refund_completed': ticket.refund_completed, 'qr_code_hash': ticket.qr_code_hash if event.status == 'confirmed' and ticket.status == 'paid' else None, 'event': event_data(db, event)}
    def qr(ticket): return hmac.new(settings.jwt_secret.encode(), f'{ticket.event_id}:{ticket.user_id}'.encode(), hashlib.sha256).hexdigest()

    @router.get('/event-organizers')
    def organizers(db=Depends(get_db)):
        rows = db.execute(select(User.id, User.name).join(Event, Event.creator_id == User.id).where(Event.is_private == False, Event.status.in_(['completed', 'cancelled'])).distinct().order_by(User.name)).all()
        return [{'id': uid, 'name': name} for uid, name in rows]

    @router.get('/events')
    def events(archive: bool = False, category: str = '', organizer: int | None = None, order: Literal['date', 'latest'] = 'date', limit: int = Query(60, ge=1, le=100), db=Depends(get_db)):
        settle(db)
        stmt = select(Event).where(Event.is_private == False)
        stmt = stmt.where(Event.status.in_(['completed', 'cancelled']) if archive else Event.status.in_(['exploration', 'crowdfunding', 'confirmed']))
        if category: stmt = stmt.where(Event.category == category)
        if organizer: stmt = stmt.where(Event.creator_id == organizer)
        return [event_data(db, e) for e in db.scalars(stmt.order_by(Event.created_at.desc() if order == 'latest' else Event.event_date.desc() if archive else Event.event_date).limit(limit))]

    @router.post('/events', status_code=201)
    def create(data: EventIn, user=Depends(current_user), db=Depends(get_db)):
        if not (user.is_admin or user.is_organizer) and (not data.is_private or data.ticket_price): fail('Студент может создать только бесплатную приватную встречу', 403)
        event = Event(**data.model_dump(), creator_id=user.id, min_tickets_required=math.ceil(data.target_budget / data.ticket_price) if data.ticket_price else 0)
        db.add(event); db.commit(); db.refresh(event)
        return event_data(db, event)

    @router.get('/events/{event_id}')
    def detail(event_id: str, db=Depends(get_db)):
        settle(db)
        event = get_event(db, event_id)
        reviews = db.execute(select(Review, User.name).join(User, Review.user_id == User.id).where(Review.event_id == event_id).order_by(Review.created_at.desc())).all()
        return {**event_data(db, event), 'reviews': [{'id': r.id, 'rating': r.rating, 'comment': r.comment, 'name': name, 'created_at': utc(r.created_at)} for r, name in reviews]}

    @router.post('/events/{event_id}/interest')
    def interest(event_id: str, user=Depends(current_user), db=Depends(get_db)):
        event = get_event(db, event_id)
        if event.status != 'exploration': fail('Сбор интереса завершён')
        if not db.get(EventInterest, (event_id, user.id)): db.add(EventInterest(event_id=event_id, user_id=user.id))
        try: db.commit()
        except IntegrityError: db.rollback()
        return event_data(db, event)

    @router.post('/events/{event_id}/launch')
    def launch(event_id: str, data: LaunchIn, user=Depends(current_user), db=Depends(get_db)):
        event = get_event(db, event_id, True); owner(event, user)
        if event.status != 'exploration' or utc(event.deadline_date) <= now(): fail('Запуск недоступен: проверьте статус и срок сбора')
        if event.ticket_price:
            if not (user.is_admin or user.is_organizer): fail('Нужна подтверждённая роль организатора', 403)
            if not data.estimate.strip() or not data.kaspi_details.strip(): fail('Заполните смету и реквизиты доверенного лица')
            event.estimate = data.estimate; event.kaspi_details = data.kaspi_details; event.status = 'crowdfunding'
        else: event.status = 'confirmed'
        db.commit(); return event_data(db, event)

    @router.get('/events/{event_id}/payment')
    def payment(event_id: str, user=Depends(current_user), db=Depends(get_db)):
        settle(db); event = get_event(db, event_id)
        if event.status != 'crowdfunding': fail('Сбор средств закрыт')
        return {'kaspi_details': event.kaspi_details}

    @router.post('/events/{event_id}/tickets', status_code=201)
    def book(event_id: str, data: BookingIn, user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        # A write on the event serializes capacity checks on SQLite as well as PostgreSQL.
        db.execute(update(Event).where(Event.id == event_id).values(capacity=Event.capacity))
        event = get_event(db, event_id, True)
        if event.status not in ('crowdfunding', 'confirmed') or (event.ticket_price and event.status != 'crowdfunding'): fail('Бронирование закрыто')
        if db.scalar(select(Ticket).where(Ticket.event_id == event_id, Ticket.user_id == user.id)): fail('У вас уже есть билет', 409)
        count = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.event_id == event_id, Ticket.status.in_(['pending', 'paid', 'used'])))
        if count >= event.capacity: fail('Свободных мест больше нет', 409)
        if event.ticket_price:
            try:
                prefix, encoded = data.screenshot.split(',', 1)
                if prefix not in ('data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'): raise ValueError()
                raw = base64.b64decode(encoded, validate=True)
                if not raw or len(raw) > 2 * 1024 * 1024: raise ValueError()
                if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff') or (raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')): raise ValueError()
            except (ValueError, TypeError): fail('Прикрепите чек JPEG, PNG или WebP до 2 МБ')
        ticket = Ticket(event_id=event_id, user_id=user.id, status='pending' if event.ticket_price else 'paid', kaspi_transaction_screenshot=data.screenshot or None)
        if not event.ticket_price: ticket.qr_code_hash = qr(ticket)
        db.add(ticket)
        try: db.commit()
        except IntegrityError: db.rollback(); fail('У вас уже есть билет', 409)
        return ticket_data(db, ticket)

    @router.get('/me/tickets')
    def mine(user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        return [ticket_data(db, t) for t in db.scalars(select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.updated_at.desc()))]

    @router.get('/me/event-notifications')
    def notifications(user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        return [{'id': n.id, 'event_id': n.event_id, 'message': n.message} for n in db.scalars(select(EventNotification).where(EventNotification.user_id == user.id).order_by(EventNotification.created_at.desc()).limit(50))]

    @router.get('/organizer/events')
    def managed(user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        stmt = select(Event)
        if not user.is_admin: stmt = stmt.where(Event.creator_id == user.id)
        return [event_data(db, e) for e in db.scalars(stmt.order_by(Event.created_at.desc()))]

    @router.get('/events/{event_id}/attendees')
    def attendees(event_id: str, user=Depends(current_user), db=Depends(get_db)):
        settle(db); owner(get_event(db, event_id), user)
        return [{**ticket_data(db, t), 'name': u.name, 'contact': u.contact, 'screenshot': t.kaspi_transaction_screenshot} for t, u in db.execute(select(Ticket, User).join(User, Ticket.user_id == User.id).where(Ticket.event_id == event_id))]

    @router.post('/tickets/{ticket_id}/approve')
    def approve(ticket_id: str, user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        ticket = db.get(Ticket, ticket_id)
        if not ticket: fail('Билет не найден', 404)
        event = get_event(db, ticket.event_id, True); owner(event, user)
        if not (user.is_admin or user.is_organizer): fail('Нужна роль организатора', 403)
        if event.status != 'crowdfunding' or ticket.status != 'pending': fail('Подтверждение недоступно', 409)
        ticket.status = 'paid'; ticket.qr_code_hash = qr(ticket); ticket.updated_at = now()
        db.commit(); return ticket_data(db, ticket)

    @router.post('/tickets/{ticket_id}/refund')
    def refund(ticket_id: str, user=Depends(current_user), db=Depends(get_db)):
        ticket = db.get(Ticket, ticket_id)
        if not ticket: fail('Билет не найден', 404)
        event = get_event(db, ticket.event_id, True); owner(event, user)
        if event.status != 'cancelled' or ticket.status not in ('refunded', 'pending'): fail('Возврат недоступен')
        ticket.status = 'refunded'; ticket.refund_completed = True; ticket.updated_at = now()
        db.commit(); return {'ok': True}

    @router.post('/tickets/verify')
    def verify(data: VerifyIn, user=Depends(current_user), db=Depends(get_db)):
        settle(db)
        ticket = db.scalar(select(Ticket).where(Ticket.qr_code_hash == data.qr_code_hash))
        if not ticket: fail('Недействительный билет', 404)
        event = get_event(db, ticket.event_id); owner(event, user)
        if ticket.status == 'used': fail(f'Билет уже использован в {utc(ticket.used_at).isoformat()}', 409)
        if event.status != 'confirmed': fail('Билет пока не активен')
        stamp = now()
        result = db.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.status == 'paid').values(status='used', used_at=stamp, updated_at=stamp))
        if result.rowcount != 1: fail('Билет уже использован или недействителен', 409)
        db.commit(); return {'ok': True, 'name': db.get(User, ticket.user_id).name, 'event': event.title, 'used_at': stamp}

    @router.post('/events/{event_id}/reviews', status_code=201)
    def review(event_id: str, data: ReviewIn, user=Depends(current_user), db=Depends(get_db)):
        settle(db); event = get_event(db, event_id)
        if event.status != 'completed': fail('Отзывы доступны после завершения')
        if not db.scalar(select(Ticket).where(Ticket.event_id == event_id, Ticket.user_id == user.id, Ticket.status == 'used')): fail('Отзыв доступен посетившим мероприятие', 403)
        db.add(Review(event_id=event_id, user_id=user.id, **data.model_dump()))
        try: db.commit()
        except IntegrityError: db.rollback(); fail('Вы уже оставили отзыв', 409)
        return {'ok': True}

    @router.patch('/admin/users/{user_id}/organizer')
    def role(user_id: int, data: RoleIn, user=Depends(current_user), db=Depends(get_db)):
        if not user.is_admin: fail('Доступ только администратору', 403)
        target = db.get(User, user_id)
        if not target: fail('Пользователь не найден', 404)
        target.is_organizer = data.is_organizer; db.commit(); return {'ok': True}
    return router
