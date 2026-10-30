import pytest
import os
import json
import hmac
import hashlib
import urllib.parse
from unittest.mock import patch

from fastapi.testclient import TestClient
from server import app, validate_init_data
from services import pdf_generator, docx_generator, pptx_generator

client = TestClient(app)

# --- Тесты валидации Telegram initData ---
def test_validate_init_data_invalid():
    with pytest.raises(Exception):
        validate_init_data("invalid_data=123")

def test_validate_init_data_valid():
    # Генерируем валидный хэш для теста
    from config import settings
    user_data = json.dumps({"id": 123456, "first_name": "Test", "username": "test_user"})
    data = {"user": user_data, "auth_date": "1600000000"}
    
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    data["hash"] = calc_hash
    init_data = urllib.parse.urlencode(data)
    
    user = validate_init_data(init_data)
    assert user["id"] == 123456

# --- Тесты API ---
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_api_unauthorized():
    response = client.get("/api/me")
    assert response.status_code == 422  # FastAPI вернет ошибку, т.к. нет Header X-Init-Data

# --- Тесты генераторов файлов ---
@pytest.fixture
def mock_content():
    return {
        "title": "Тестовый документ",
        "subtitle": "Проверка",
        "sections": [
            {"heading": "Введение", "paragraphs": ["Тестовый абзац для проверки кириллицы."], "bullets": []},
            {"heading": "Основная часть", "paragraphs": ["Еще один абзац."], "bullets": ["Пункт 1", "Пункт 2"]}
        ],
        "conclusion": "Всё работает.",
        "sources": ["Тестовый источник"]
    }

@pytest.fixture
def mock_options():
    return {
        "doc_type": "доклад",
        "include_title_page": True,
        "include_toc": True,
        "include_conclusion": True,
        "include_sources": True
    }

def test_pdf_generator(mock_content, mock_options, tmp_path):
    file_path = pdf_generator.generate(mock_content, mock_options, str(tmp_path))
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 0
    assert file_path.endswith(".pdf")

def test_docx_generator(mock_content, mock_options, tmp_path):
    file_path = docx_generator.generate(mock_content, mock_options, str(tmp_path))
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 0
    assert file_path.endswith(".docx")

def test_pptx_generator(mock_content, mock_options, tmp_path):
    file_path = pptx_generator.generate(mock_content, mock_options, str(tmp_path))
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 0
    assert file_path.endswith(".pptx")
