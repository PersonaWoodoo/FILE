from services import pdf_generator, docx_generator, pptx_generator

content = {
    "title": "Тестовый документ",
    "subtitle": "Проверка генераторов",
    "sections": [
        {"heading": "Введение", "paragraphs": ["Это тестовый абзац для проверки кириллицы и вёрстки. " * 5], "bullets": []},
        {"heading": "Основная часть", "paragraphs": ["Ещё один абзац. " * 8], "bullets": ["Пункт 1", "Пункт 2", "Пункт 3"]},
    ],
    "sources": ["ГОСТ 7.32-2017"],
    "conclusion": "Всё работает.",
}
options = {"doc_type": "доклад", "include_title_page": True, "include_toc": True,
           "include_conclusion": True, "include_sources": True}

print("PDF:", pdf_generator.generate(content, options, "generated"))
print("DOCX:", docx_generator.generate(content, options, "generated"))
print("PPTX:", pptx_generator.generate(content, options, "generated"))
