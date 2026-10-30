from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session

from models import User, Document
from services.telegram_service import send_document_to_user

router = Router()


@router.callback_query(F.data.startswith("doc_send:"))
async def send_doc_to_tg(callback: CallbackQuery, session: Session, bot):
    doc_id = int(callback.data.split(":", 1)[1])
    user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    doc = session.query(Document).filter(
        Document.id == doc_id, Document.user_id == user.id
    ).first()
    if not doc:
        await callback.answer("Документ не найден", show_alert=True)
        return
    ok = await send_document_to_user(
        bot, user.telegram_id, doc.file_path, doc.title, doc.format,
    )
    await callback.answer("Отправлено ✅" if ok else "Ошибка отправки", show_alert=True)
