import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import Payment, User
from services.subscription_service import PLANS, grant_premium

log = logging.getLogger(__name__)


def create_pending_payment(session: Session, telegram_id: int, plan_key: str) -> Payment:
    plan = PLANS.get(plan_key)
    if not plan:
        raise ValueError(f"Неизвестный тариф: {plan_key}")

    payment = Payment(
        telegram_id=telegram_id,
        plan=plan_key,
        stars_amount=plan["stars"],
        status="pending",
    )
    session.add(payment)
    session.flush()
    return payment


def verify_pre_checkout(
    session: Session, telegram_id: int, invoice_payload: str, amount: int, currency: str
) -> tuple[bool, str]:
    if currency != "XTR":
        return False, "Неверная валюта"

    try:
        _, plan_key, payment_id_str = invoice_payload.split(":")
        payment_id = int(payment_id_str)
    except Exception:
        return False, "Некорректный payload"

    plan = PLANS.get(plan_key)
    if not plan:
        return False, "Неизвестный тариф"

    payment = session.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return False, "Платёж не найден"
    if payment.status != "pending":
        return False, "Платёж уже обработан"
    if payment.telegram_id != telegram_id:
        return False, "Платёж принадлежит другому пользователю"
    if payment.stars_amount != amount:
        return False, "Неверная сумма"
    if payment.stars_amount != plan["stars"]:
        return False, "Сумма не соответствует тарифу"

    return True, ""


def confirm_payment(
    session: Session,
    telegram_id: int,
    invoice_payload: str,
    charge_id: str,
    total_amount: int,
    currency: str,
) -> Optional[User]:
    if currency != "XTR":
        log.warning("confirm_payment: неверная валюта %s", currency)
        return None

    dup = session.query(Payment).filter(Payment.charge_id == charge_id).first()
    if dup and dup.status == "paid":
        log.info("Повторный charge_id %s — пропускаем", charge_id)
        return None

    try:
        _, plan_key, payment_id_str = invoice_payload.split(":")
        payment_id = int(payment_id_str)
    except Exception:
        log.warning("confirm_payment: некорректный payload %s", invoice_payload)
        return None

    plan = PLANS.get(plan_key)
    if not plan:
        return None

    payment = session.query(Payment).filter(Payment.id == payment_id).first()
    if not payment or payment.telegram_id != telegram_id:
        return None
    if payment.status == "paid":
        log.info("Платёж %s уже оплачен", payment_id)
        return None
    if total_amount != plan["stars"]:
        log.warning("confirm_payment: сумма %s не совпадает с тарифом %s", total_amount, plan["stars"])
        return None

    payment.charge_id = charge_id
    payment.status = "paid"

    try:
        user = grant_premium(session, telegram_id, plan["days"])
    except Exception as e:
        log.exception("grant_premium failed: %s", e)
        payment.status = "error"
        return None

    log.info("Платёж OK: user=%s plan=%s stars=%s charge=%s", telegram_id, plan_key, plan["stars"], charge_id)
    return user


def mark_refunded(session: Session, charge_id: str, telegram_id: int) -> bool:
    payment = session.query(Payment).filter(Payment.charge_id == charge_id).first()
    if not payment:
        log.warning("Возврат: charge %s не найден", charge_id)
        return False
    if payment.status != "paid":
        return False
    
    payment.status = "refunded"

    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    plan = PLANS.get(payment.plan)
    if user and plan:
        if user.premium_until:
            new_until = user.premium_until - timedelta(days=plan["days"])
            user.premium_until = new_until if new_until > datetime.utcnow() else None
            if user.premium_until is None:
                user.premium_generations_left = 0
                
    log.info("Возврат: charge=%s user=%s plan=%s", charge_id, telegram_id, payment.plan)
    return True


def user_payments(session: Session, telegram_id: int, limit: int = 20) -> list[Payment]:
    return (
        session.query(Payment)
        .filter(Payment.telegram_id == telegram_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .all()
    )
