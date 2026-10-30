from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, CallbackQuery,
)
from sqlalchemy.orm import Session

from config import settings
from models import User, Referral
from services.telegram_service import mini_app_url

router = Router()


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть DocuFlow AI",
            web_app=WebAppInfo(url=mini_app_url()),
        )],
        [
            InlineKeyboardButton(text="💎 Premium", callback_data="menu:premium"),
            InlineKeyboardButton(text="📂 Мои документы", callback_data="menu:documents"),
        ],
        [
            InlineKeyboardButton(text="🎁 Пригласить друга", callback_data="menu:referral"),
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu:support"),
        ],
    ])


WELCOME_TEXT = (
    "🚀 <b>Добро пожаловать в DocuFlow AI!</b>\n\n"
    "Создавайте красивые документы и презентации с помощью искусственного интеллекта.\n\n"
    "📄 Доклады и рефераты\n"
    "📊 Презентации\n"
    "📝 Эссе и статьи\n"
    "📚 Конспекты\n"
    "✨ Оформление за несколько минут\n\n"
    "🎁 <b>Первая генерация бесплатно!</b>\n\n"
    "Нажмите кнопку ниже, чтобы начать."
)


def _ensure_user(session: Session, tg) -> User:
    user = session.query(User).filter(User.telegram_id == tg.id).first()
    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            language_code=tg.language_code or "ru",
            free_generations_left=settings.free_generations,
            premium_generations_left=0,
        )
        session.add(user)
        session.flush()
    return user


@router.message(CommandStart())
async def cmd_start(message: Message, session: Session, command: CommandStart):
    user = _ensure_user(session, message.from_user)

    args = command.args
    if args and args.startswith("ref_") and user.referrer_id is None:
        try:
            ref_id = int(args[4:])
        except ValueError:
            ref_id = None
        if ref_id and ref_id != message.from_user.id:
            referrer = session.query(User).filter(User.telegram_id == ref_id).first()
            exists = session.query(Referral).filter(
                Referral.invited_telegram_id == message.from_user.id
            ).first()
            if referrer and not exists:
                user.referrer_id = ref_id
                referrer.referrals_count += 1
                session.add(Referral(
                    referrer_telegram_id=ref_id,
                    invited_telegram_id=message.from_user.id,
                ))
                if referrer.referrals_count == 5:
                    referrer.free_generations_left += 3
                if referrer.referrals_count == 10:
                    from services.subscription_service import grant_premium
                    grant_premium(session, ref_id, 7)

    await message.answer(WELCOME_TEXT, reply_markup=_main_menu_kb())


@router.message(Command("app"))
async def cmd_app(message: Message):
    await message.answer(
        "Открыть приложение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Открыть DocuFlow AI",
                web_app=WebAppInfo(url=mini_app_url()),
            ),
        ]]),
    )


@router.message(Command("premium"))
async def cmd_premium(message: Message):
    from handlers.payments import send_plans
    await send_plans(message)


@router.message(Command("documents"))
async def cmd_documents(message: Message, session: Session):
    from models import Document
    user = _ensure_user(session, message.from_user)
    docs = (
        session.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .limit(10)
        .all()
    )
    if not docs:
        await message.answer("📂 У вас пока нет документов.\nОткройте приложение и создайте первый!")
        return
    lines = ["📂 <b>Последние документы:</b>\n"]
    for d in docs:
        lines.append(f"• {d.title[:60]} — {d.format.upper()} — {d.created_at:%d.%m.%Y}")
    await message.answer("\n".join(lines))


@router.message(Command("referral"))
async def cmd_referral(message: Message, session: Session):
    user = _ensure_user(session, message.from_user)
    link = f"https://t.me/{settings.bot_username}?start=ref_{user.telegram_id}"
    await message.answer(
        f"🎁 <b>Реферальная программа</b>\n\n"
        f"Приглашено друзей: <b>{user.referrals_count}</b>\n\n"
        f"5 друзей → +3 генерации\n"
        f"10 друзей → 7 дней Premium\n\n"
        f"Ваша ссылка:\n<code>{link}</code>",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🆘 <b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/app — открыть приложение\n"
        "/premium — тарифы\n"
        "/documents — мои документы\n"
        "/referral — реферальная ссылка\n"
        "/help — помощь\n\n"
        "Канал: @DocuFlowAI"
    )


@router.callback_query(F.data.startswith("menu:"))
async def menu_callback(callback: CallbackQuery, session: Session):
    action = callback.data.split(":", 1)[1]
    if action == "premium":
        from handlers.payments import send_plans
        await send_plans(callback.message, edit=True)
    elif action == "documents":
        from models import Document
        user = _ensure_user(session, callback.from_user)
        docs = (
            session.query(Document)
            .filter(Document.user_id == user.id)
            .order_by(Document.created_at.desc())
            .limit(10)
            .all()
        )
        if not docs:
            text = "📂 У вас пока нет документов."
        else:
            text = "📂 <b>Последние документы:</b>\n\n" + "\n".join(
                f"• {d.title[:60]} — {d.format.upper()}" for d in docs
            )
        await callback.message.answer(text)
    elif action == "referral":
        await cmd_referral(callback.message, session)
    elif action == "support":
        await callback.message.answer(
            "🆘 Поддержка: @DocuFlowAI\nКанал: @DocuFlowAI"
        )
    await callback.answer()
