import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from datetime import datetime
from typing import Any, Optional

from fastapi import (
    FastAPI, Header, HTTPException, Request, UploadFile, File, Depends, Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import get_session, init_db
from models import User, Document, Payment, Referral
from services import ai_service

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("docuflow.server")

os.makedirs(settings.generated_dir, exist_ok=True)
os.makedirs(settings.data_dir, exist_ok=True)

init_db()

app = FastAPI(title="DocuFlow AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_url, "https://web.telegram.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Telegram initData validation ----------

def validate_init_data(init_data: str) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(401, "initData отсутствует")
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise HTTPException(401, "initData некорректен")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "hash отсутствует")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()
    calc_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise HTTPException(401, "Подпись initData неверна")

    auth_date = int(parsed.get("auth_date", "0") or 0)
    if auth_date and time.time() - auth_date > 86400:
        raise HTTPException(401, "initData устарел")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(401, "user отсутствует в initData")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(401, "user некорректен")

    return user


def get_current_user(
    init_data: str = Header(..., alias="X-Init-Data"),
) -> dict[str, Any]:
    return validate_init_data(init_data)


def ensure_user(session: Session, tg_user: dict[str, Any]) -> User:
    tg_id = int(tg_user["id"])
    user = session.query(User).filter(User.telegram_id == tg_id).first()
    if not user:
        user = User(
            telegram_id=tg_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            language_code=tg_user.get("language_code", "ru"),
            free_generations_left=settings.free_generations,
            premium_generations_left=0,
        )
        session.add(user)
        session.flush()
    else:
        user.username = tg_user.get("username") or user.username
        user.first_name = tg_user.get("first_name") or user.first_name
        user.last_seen_at = datetime.utcnow()
    return user


# ---------- Schemas ----------

class GenerateRequest(BaseModel):
    doc_type: str = Field(..., min_length=2, max_length=64)
    format: str = Field("pdf", pattern="^(pdf|docx|pptx)$")
    topic: str = Field(..., min_length=2, max_length=500)
    extra: str = ""
    language: str = "ru"
    difficulty: str = "средний"
    style: str = "нейтральный"
    pages: int = Field(5, ge=1, le=30)
    include_title_page: bool = True
    include_toc: bool = True
    include_conclusion: bool = True
    include_sources: bool = False


# ---------- Routes ----------

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/me")
async def api_me(tg_user: dict = Depends(get_current_user)):
    with get_session() as session:
        user = ensure_user(session, tg_user)
        is_premium = user.is_premium()
        return {
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "username": user.username,
            "is_premium": is_premium,
            "premium_until": user.premium_until.isoformat() if user.premium_until else None,
            "free_generations_left": user.free_generations_left,
            "premium_generations_left": user.premium_generations_left,
            "referrals_count": user.referrals_count,
        }


@app.get("/api/documents")
async def api_documents(tg_user: dict = Depends(get_current_user)):
    with get_session() as session:
        user = ensure_user(session, tg_user)
        docs = (
            session.query(Document)
            .filter(Document.user_id == user.id)
            .order_by(Document.created_at.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "id": d.id,
                "title": d.title,
                "doc_type": d.doc_type,
                "format": d.format,
                "file_size": d.file_size,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]


@app.get("/api/documents/{doc_id}/download")
async def api_download(
    doc_id: int,
    tg_user: dict = Depends(get_current_user),
):
    with get_session() as session:
        user = ensure_user(session, tg_user)
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if not doc or doc.user_id != user.id:
            raise HTTPException(404, "Документ не найден")
        if not os.path.exists(doc.file_path):
            raise HTTPException(410, "Файл удалён")
        return FileResponse(
            doc.file_path,
            filename=os.path.basename(doc.file_path),
        )


@app.delete("/api/documents/{doc_id}")
async def api_delete_document(
    doc_id: int,
    tg_user: dict = Depends(get_current_user),
):
    with get_session() as session:
        user = ensure_user(session, tg_user)
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if not doc or doc.user_id != user.id:
            raise HTTPException(404, "Документ не найден")
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except OSError:
            pass
        session.delete(doc)
        return {"ok": True}


@app.post("/api/generate")
async def api_generate(
    payload: GenerateRequest,
    tg_user: dict = Depends(get_current_user),
):
    from services import pdf_generator, docx_generator, pptx_generator

    with get_session() as session:
        user = ensure_user(session, tg_user)
        if user.is_blocked:
            raise HTTPException(403, "Пользователь заблокирован")

        if user.is_premium() and user.premium_generations_left > 0:
            user.premium_generations_left -= 1
        elif not user.is_premium() and user.free_generations_left > 0:
            user.free_generations_left -= 1
        elif user.is_premium() and user.premium_generations_left <= 0:
            raise HTTPException(402, "Лимит Premium-генераций исчерпан")
        else:
            raise HTTPException(402, "Лимит генераций исчерпан. Оформите Premium.")

        doc_type = payload.doc_type
        fmt = payload.format
        topic = payload.topic
        user_id = user.id

    try:
        content = await ai_service.generate_document(payload.model_dump())
    except ai_service.AIError as e:
        log.error("AI error: %s", e)
        # вернуть генерацию обратно
        with get_session() as session:
            u = session.query(User).filter(User.id == user_id).first()
            if u:
                if u.is_premium():
                    u.premium_generations_left += 1
                else:
                    u.free_generations_left += 1
        raise HTTPException(502, f"Ошибка AI: {e}")

    try:
        if fmt == "pdf":
            file_path = pdf_generator.generate(content, payload.model_dump(), settings.generated_dir)
        elif fmt == "docx":
            file_path = docx_generator.generate(content, payload.model_dump(), settings.generated_dir)
        else:
            file_path = pptx_generator.generate(content, payload.model_dump(), settings.generated_dir)
    except Exception as e:
        log.exception("Генерация файла упала")
        raise HTTPException(500, f"Ошибка генерации файла: {e}")

    file_size = os.path.getsize(file_path)

    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        doc = Document(
            user_id=user.id,
            title=content["title"][:250],
            doc_type=doc_type,
            format=fmt,
            file_path=file_path,
            file_size=file_size,
            status="done",
        )
        session.add(doc)
        session.flush()
        doc_id = doc.id

    return {
        "id": doc_id,
        "title": content["title"],
        "format": fmt,
        "file_size": file_size,
        "download_url": f"/api/documents/{doc_id}/download",
    }


# ---------- Admin ----------

def require_admin(tg_user: dict = Depends(get_current_user)) -> dict:
    if int(tg_user["id"]) not in settings.admin_ids:
        raise HTTPException(403, "Доступ только для админа")
    return tg_user


@app.get("/api/admin/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    with get_session() as session:
        total_users = session.query(User).count()
        total_docs = session.query(Document).count()
        premium_users = session.query(User).filter(
            User.premium_until != None, User.premium_until > datetime.utcnow()  # noqa
        ).count()
        total_payments = session.query(Payment).filter(Payment.status == "paid").count()
        return {
            "total_users": total_users,
            "total_documents": total_docs,
            "premium_users": premium_users,
            "total_payments": total_payments,
        }


# ---------- Frontend ----------

frontend_path = os.path.join(os.path.dirname(__file__), settings.frontend_dir)
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=settings.port, workers=1)
