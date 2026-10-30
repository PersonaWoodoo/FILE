import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models import User, SubscriptionEvent

log = logging.getLogger(__name__)

PLANS = {
    "premium_7":  {"days": 7,  "stars": 50,  "title": "Premium 7 дней"},
    "premium_15": {"days": 15, "stars": 150, "title": "Premium 15 дней"},
    "premium_30": {"days": 30, "stars": 250, "title": "Premium 30 дней"},
}


def grant_premium(session: Session, telegram_id: int, days: int) -> User:
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise ValueError(f"Пользователь {telegram_id} не найден")
    now = datetime.utcnow()
    base = user.premium_until if user.premium_until and user.premium_until > now else now
    user.premium_until = base + timedelta(days=days)
    user.premium_generations_left += 100
    session.add(SubscriptionEvent(
        telegram_id=telegram_id, action="grant", days=days,
    ))
    return user


def revoke_premium(session: Session, telegram_id: int) -> User:
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise ValueError(f"Пользователь {telegram_id} не найден")
    user.premium_until = None
    user.premium_generations_left = 0
    session.add(SubscriptionEvent(
        telegram_id=telegram_id, action="revoke", days=0,
    ))
    return user
