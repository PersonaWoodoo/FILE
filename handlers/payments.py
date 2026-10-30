from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)
from sqlalchemy.orm import Session

from config import settings
from models import Payment, User
from services.subscription_service import PLANS, grant_premium

router = Router()


def _plans_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💎 Premium 7 дней — {PLANS['premium_7']['stars']} ⭐",
            callback_data="buy:premium_7",
        )],
        [InlineKeyboardButton(
            text=f"💎 Premium 15 дней — {PLANS['premium_15']['stars']} ⭐",
            callback_data="buy:premium_15",
        )],
        [InlineKeyboardButton(
            text=f"💎 Premium 30 дней — {PLANS['premium_30']['stars']} ⭐",
            callback_data="buy:premium_30",
        )],
    ])


async def send_plans(message: Message, edit: bool = False):
    text = (
        "💎 <b>DocuFlow Premium</b>\n\n"
        "• Безлимитные генерации документов\n"
        "• Приоритетная очередь\n"
        "• Все форматы: PDF, DOCX, PPTX\n\n"
        "Выберите тариф:"
    )
    if edit:
        try:
            await message.edit_text(text, reply_markup=_plans_kb())
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=_plans_kb())


@router.message(F.text == "/premium")
async def premium_cmd(message: Message):
    await send_plans(message)


@router.callback_query(F.data.startswith("buy:"))
async def buy_plan(callback: CallbackQuery, session: Session, bot):
    plan_key = callback.data.split(":", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return

    payment = Payment(
        telegram_id=callback.from_user.id,
        plan=plan_key,
        stars_amount=plan["stars"],
        status="pending",
    )
    session.add(payment)
    session.flush()
    payment_id = payment.id

    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=plan["title"],
            description=f"Подписка DocuFlow AI: {plan['days']} дней Premium",
            payload=f"plan:{plan_key}:{payment_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(
                label=plan["title"],
                amount=plan["stars"],
            )],
        )
    except Exception as e:
        await callback.answer(f"Ошибка выставления счёта: {e}", show_alert=True)
        return

    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: Session):
    try:
        _, plan_key, payment_id_str = query.invoice_payload.split(":")
        payment_id = int(payment_id_str)
    except Exception:
        await query.answer(ok=False, error_message="Некорректный платёж")
        return

    payment = session.query(Payment).filter(Payment.id == payment_id).first()
    plan = PLANS.get(plan_key)
    if (
        not payment
        or not plan
        or payment.status != "pending"
        or payment.telegram_id != query.from_user.id
        or payment.stars_amount != plan["stars"]
    ):
        await query.answer(ok=False, error_message="Платёж не найден или устарел")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: Session):
    sp = message.successful_payment
    charge_id = sp.telegram_payment_charge_id

    existing = session.query(Payment).filter(Payment.charge_id == charge_id).first()
    if existing and existing.status == "paid":
        return

    try:
        _, plan_key, payment_id_str = sp.invoice_payload.split(":")
        payment_id = int(payment_id_str)
    except Exception:
        return

    payment = session.query(Payment).filter(Payment.id == payment_id).first()
    plan = PLANS.get(plan_key)
    if not payment or not plan:
        return

    payment.charge_id = charge_id
    payment.status = "paid"

    grant_premium(session, message.from_user.id, plan["days"])

    await message.answer(
        f"✅ <b>Оплата успешна!</b>\n\n"
        f"Тариф: {plan['title']}\n"
        f"Дней Premium начислено: {plan['days']}\n\n"
        f"Спасибо, что выбрали DocuFlow AI!"
    )
