import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)
from sqlalchemy.orm import Session

from services import payment_service
from services.subscription_service import PLANS

log = logging.getLogger(__name__)
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
        "• Расширенные лимиты генераций\n"
        "• Приоритетная очередь\n"
        "• PDF, DOCX, PPTX без ограничений\n\n"
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

    try:
        payment = payment_service.create_pending_payment(
            session, callback.from_user.id, plan_key,
        )
        payload = f"plan:{plan_key}:{payment.id}"
        
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=plan["title"],
            description=f"Подписка DocuFlow AI: {plan['days']} дней",
            payload=payload,
            provider_token="", # Для Stars токен провайдера пустой
            currency="XTR",    # XTR = Telegram Stars
            prices=[LabeledPrice(label=plan["title"], amount=plan["stars"])],
        )
        await callback.answer()
    except Exception as e:
        log.exception("Не удалось выставить счёт")
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: Session):
    ok, err = payment_service.verify_pre_checkout(
        session,
        telegram_id=query.from_user.id,
        invoice_payload=query.invoice_payload,
        amount=query.total_amount,
        currency=query.currency,
    )
    if not ok:
        log.warning("pre_checkout отклонён: %s", err)
    await query.answer(ok=ok, error_message=err or None)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: Session):
    sp = message.successful_payment
    user = payment_service.confirm_payment(
        session,
        telegram_id=message.from_user.id,
        invoice_payload=sp.invoice_payload,
        charge_id=sp.telegram_payment_charge_id,
        total_amount=sp.total_amount,
        currency=sp.currency,
    )
    if not user:
        await message.answer(
            "⚠️ Платёж получен, но не удалось активировать Premium. "
            "Напишите в поддержку: @DocuFlowAI"
        )
        return

    until = user.premium_until.strftime("%d.%m.%Y") if user.premium_until else "—"
    await message.answer(
        f"✅ <b>Оплата успешна!</b>\n\n"
        f"Premium активен до: <b>{until}</b>\n\n"
        f"Спасибо, что выбрали DocuFlow AI!"
    )


@router.message(F.refunded_payment)
async def on_refunded_payment(message: Message, session: Session):
    rp = message.refunded_payment
    payment_service.mark_refunded(
        session,
        charge_id=rp.telegram_payment_charge_id,
        telegram_id=message.from_user.id,
    )
    await message.answer("↩️ Возврат обработан. Premium скорректирован.")


@router.message(F.text == "/payments")
async def my_payments(message: Message, session: Session):
    rows = payment_service.user_payments(session, message.from_user.id)
    if not rows:
        await message.answer("История платежей пуста.")
        return
    lines = ["💰 <b>История платежей</b>\n"]
    for p in rows:
        status_map = {
            "pending": "⏳ ожидает",
            "paid": "✅ оплачен",
            "refunded": "↩️ возврат",
            "error": "⚠️ ошибка",
        }
        lines.append(
            f"• {PLANS.get(p.plan, {}).get('title', p.plan)} — "
            f"{p.stars_amount} ⭐ — {status_map.get(p.status, p.status)} — "
            f"{p.created_at:%d.%m.%Y}"
        )
    await message.answer("\n".join(lines))
