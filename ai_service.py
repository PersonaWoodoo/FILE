import json
import logging
import re
from typing import Any

import httpx

from config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — профессиональный ассистент по созданию учебных и деловых документов на русском языке.
Ты возвращаешь ТОЛЬКО валидный JSON без markdown, без пояснений, без ```json.
Структура JSON строго такая:

{
  "title": "Заголовок документа",
  "subtitle": "Подзаголовок или пустая строка",
  "sections": [
    {
      "heading": "Заголовок раздела",
      "paragraphs": ["абзац 1", "абзац 2"],
      "bullets": ["пункт 1", "пункт 2"]
    }
  ],
  "sources": ["Источник 1", "Источник 2"],
  "conclusion": "Текст заключения"
}

Правила:
- Язык — русский (если пользователь не попросил другой).
- Текст содержательный, без воды и повторов.
- Не выдумывай конкретные библиографические ссылки (автор, год, ISBN). В "sources" пиши только общие направления/типы источников, если пользователь не дал реальные.
- Если sources не нужны — верни пустой массив [].
- Если conclusion не нужен — верни пустую строку "".
- bullets — массив строк, может быть пустым [].
- paragraph — массив строк, минимум 1 абзац на раздел.
- Никакого текста вне JSON.
"""


class AIError(Exception):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise AIError("AI вернул не JSON")
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise AIError(f"Не удалось разобрать JSON: {e}")


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AIError("Ответ AI — не объект")

    title = str(data.get("title") or "").strip()
    if not title:
        raise AIError("AI не вернул title")

    sections = data.get("sections") or []
    if not isinstance(sections, list) or not sections:
        raise AIError("AI не вернул sections")

    clean_sections = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading") or "").strip()
        paragraphs = [str(p).strip() for p in (s.get("paragraphs") or []) if str(p).strip()]
        bullets = [str(b).strip() for b in (s.get("bullets") or []) if str(b).strip()]
        if not heading and not paragraphs and not bullets:
            continue
        clean_sections.append({
            "heading": heading or "Раздел",
            "paragraphs": paragraphs,
            "bullets": bullets,
        })

    if not clean_sections:
        raise AIError("AI вернул пустые sections")

    sources = [str(x).strip() for x in (data.get("sources") or []) if str(x).strip()]
    conclusion = str(data.get("conclusion") or "").strip()

    return {
        "title": title,
        "subtitle": str(data.get("subtitle") or "").strip(),
        "sections": clean_sections,
        "sources": sources,
        "conclusion": conclusion,
    }


def _build_user_prompt(payload: dict[str, Any]) -> str:
    doc_type = payload.get("doc_type", "доклад")
    topic = payload.get("topic", "").strip()
    extra = payload.get("extra", "").strip()
    language = payload.get("language", "ru")
    difficulty = payload.get("difficulty", "средний")
    style = payload.get("style", "нейтральный")
    pages = payload.get("pages", 5)
    include_sources = bool(payload.get("include_sources", False))
    include_conclusion = bool(payload.get("include_conclusion", True))

    parts = [
        f"Тип документа: {doc_type}",
        f"Тема: {topic}",
        f"Язык: {language}",
        f"Уровень сложности: {difficulty}",
        f"Стиль изложения: {style}",
        f"Ориентировочный объём: {pages} страниц(ы)",
        f"Включить заключение: {'да' if include_conclusion else 'нет'}",
        f"Включить список источников: {'да' if include_sources else 'нет'}",
    ]
    if extra:
        parts.append(f"Обязательно включить: {extra}")
    parts.append("Верни строго JSON по заданной схеме.")
    return "\n".join(parts)


async def generate_document(payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{settings.ai_base_url}chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(payload)},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }

    last_err: Exception | None = None
    for attempt in range(1, 3):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(url, headers=headers, json=body)
            if r.status_code >= 400:
                log.warning("Gemini HTTP %s: %s", r.status_code, r.text[:300])
                raise AIError(f"Gemini вернул {r.status_code}")
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            return _validate(parsed)
        except (httpx.HTTPError, KeyError, AIError, json.JSONDecodeError) as e:
            last_err = e
            log.warning("Попытка %s не удалась: %s", attempt, e)

    raise AIError(f"Не удалось получить документ от AI: {last_err}")
