MESSAGES = {
    "en": {
        "description": "Local-first transcript-driven conference video cutter.",
        "doctor_help": "Check local tools required for conference video processing.",
        "doctor_ok": "Local tool check passed.",
        "missing_tools": "Missing local tools: {tools}",
        "init_help": "Create a project file.",
        "validate_help": "Validate a project file.",
        "transcript_help": "Render a transcript as Markdown.",
        "render_help": "Render reviewed clips.",
        "input_help": "Source video path.",
        "output_help": "Project JSON path to create.",
        "project_help": "Project JSON path.",
        "transcript_output_help": "Markdown output path.",
        "accurate_help": "Decode and re-encode for accurate boundaries.",
        "project_valid": "Project is valid.",
        "transcript_not_found": "Transcript not found: {path}",
        "transcript_decode_warning": "Transcript had invalid UTF-8 bytes; replaced them with U+FFFD.",
        "rendered": "Rendered {count} clips.",
        "render_warnings": "Boundary warnings: {count}. Use --accurate for frame-accurate cuts.",
    },
    "ru": {
        "description": "Локальная нарезка конференций по транскрипту.",
        "doctor_help": "Проверить локальные инструменты для обработки видео конференции.",
        "doctor_ok": "Проверка локальных инструментов пройдена.",
        "missing_tools": "Не найдены локальные инструменты: {tools}",
        "init_help": "Создать файл проекта.",
        "validate_help": "Проверить файл проекта.",
        "transcript_help": "Сформировать транскрипт в Markdown.",
        "render_help": "Нарезать проверенные клипы.",
        "input_help": "Путь к исходному видео.",
        "output_help": "Путь к создаваемому JSON-проекту.",
        "project_help": "Путь к JSON-проекту.",
        "transcript_output_help": "Путь к Markdown-файлу.",
        "accurate_help": "Декодировать и перекодировать для точных границ.",
        "project_valid": "Проект корректен.",
        "transcript_not_found": "Транскрипт не найден: {path}",
        "transcript_decode_warning": "В транскрипте были некорректные байты UTF-8; они заменены на U+FFFD.",
        "rendered": "Нарезано клипов: {count}.",
        "render_warnings": "Предупреждений о границах: {count}. Для точной нарезки используйте --accurate.",
    },
}


def message(lang: str, key: str, **values: object) -> str:
    language = lang if lang in MESSAGES else "en"
    return MESSAGES[language][key].format(**values)
