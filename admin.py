import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session

from config import settings
from models import User, Document, Payment
from services.subscription_service import grant_premium, revoke_premium

log = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return

    total_users = session.query(User).count()
    total_docs = session.query(Document).count()
    premium_users = session.query(User).filter(
        User.premium_until != None, User.premium_until > datetime.utcnow()  # noqa
    ).count()
    total_paid = session.query(Payment).filter(Payment.status == "paid").count()

    await message.answer(
        f"👑 <b>Админ-панель DocuFlow AI</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📄 Документов: <b>{total_docs}</b>\n"
        f"💎 Premium: <b>{premium_users}</b>\n"
        f"💰 Платежей: <b>{total_paid}</b>\n\n"
        f"Команды:\n"
        f"/grant &lt;telegram_id&gt; &lt;days&gt; — выдать Premium\n"
        f"/revoke &lt;telegram_id&gt; — отозвать Premium\n"
        f"/user &lt;telegram_id&gt; — профиль\n"
        f"/block &lt;telegram_id&gt; — блокировать\n"
        f"/unblock &lt;telegram_id&gt; — разблокировать\n"
        f"/addgens &lt;telegram_id&gt; &lt;n&gt; — добавить генерации"
    )


@router.message(Command("grant"))
async def admin_grant(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /grant <telegram_id> <days>")
        return
    try:
        tg_id, days = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Неверные аргументы")
        return
    try:
        user = grant_premium(session, tg_id, days)
        await message.answer(
            f"✅ Premium выдан пользователю {tg_id} до {user.premium_until:%d.%m.%Y %H:%M}"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("revoke"))
async def admin_revoke(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /revoke <telegram_id>")
        return
    try:
        tg_id = int(parts[1])
        revoke_premium(session, tg_id)
        await message.answer(f"✅ Premium отозван у {tg_id}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("user"))
async def admin_user(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /user <telegram_id>")
        return
    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID")
        return
    user = session.query(User).filter(User.telegram_id == tg_id).first()
    if not user:
        await message.answer("Пользователь не найден")
        return
    docs_count = session.query(Document).filter(Document.user_id == user.id).count()
    await message.answer(
        f"👤 <b>{user.first_name or ''} @{user.username or ''}</b>\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Premium: {'✅ до ' + user.premium_until.strftime('%d.%m.%Y') if user.is_premium() else '❌'}\n"
        f"Бесплатных генераций: {user.free_generations_left}\n"
        f"Premium-генераций: {user.premium_generations_left}\n"
        f"Документов: {docs_count}\n"
        f"Рефералов: {user.referrals_count}\n"
        f"Заблокирован: {'да' if user.is_blocked else 'нет'}"
    )


@router.message(Command("block"))
async def admin_block(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        return
    try:
        tg_id = int(parts[1])
    except ValueError:
        return
    user = session.query(User).filter(User.telegram_id == tg_id).first()
    if user:
        user.is_blocked = True
        await message.answer(f"⛔ {tg_id} заблокирован")


@router.message(Command("unblock"))
async def admin_unblock(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        return
    try:
        tg_id = int(parts[1])
    except ValueError:
        return
    user = session.query(User).filter(User.telegram_id == tg_id).first()
    if user:
        user.is_blocked = False
        await message.answer(f"✅ {tg_id} разблокирован")


@router.message(Command("addgens"))
async def admin_addgens(message: Message, session: Session):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        return
    try:
        tg_id, n = int(parts[1]), int(parts[2])
    except ValueError:
        return
    user = session.query(User).filter(User.telegram_id == tg_id).first()
    if not user:
        await message.answer("Пользователь не найден")
        return
    if user.is_premium():
        user.premium_generations_left += n
    else:
        user.free_generations_left += n
    await message.answer(f"✅ {tg_id}: +{n} генераций")
