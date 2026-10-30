from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean,
    ForeignKey, Text,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    language_code = Column(String(8), default="ru")

    premium_until = Column(DateTime, nullable=True)
    free_generations_left = Column(Integer, default=1)
    premium_generations_left = Column(Integer, default=0)

    referrer_id = Column(BigInteger, nullable=True)
    referrals_count = Column(Integer, default=0)

    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")

    def is_premium(self) -> bool:
        return bool(self.premium_until and self.premium_until > datetime.utcnow())


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    doc_type = Column(String(32), nullable=False)
    format = Column(String(8), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, default=0)
    status = Column(String(16), default="done")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    plan = Column(String(32), nullable=False)
    stars_amount = Column(Integer, nullable=False)
    charge_id = Column(String(128), unique=True, nullable=True)
    status = Column(String(16), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_telegram_id = Column(BigInteger, nullable=False, index=True)
    invited_telegram_id = Column(BigInteger, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    action = Column(String(32), nullable=False)
    days = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
