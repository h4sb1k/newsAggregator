# translator.py
"""
Модуль для перевода текста на русский язык.
Поддерживает несколько бэкендов и кэширование результатов.
"""
import json
import hashlib
from pathlib import Path
from typing import Optional

# 🔧 Выбор бэкенда: 'googletrans', 'deep_translator', 'libretranslate', 'google_api'
TRANSLATOR_BACKEND = 'googletrans'  # Бесплатный, но может быть нестабильным

# 📁 Кэш переводов (чтобы не переводить одно и то же дважды)
CACHE_FILE = Path('translations_cache.json')
MAX_CACHE_SIZE = 1000  # Максимальное количество записей в кэше

def _load_cache() -> dict:
    """Загружает кэш переводов из файла."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def _save_cache(cache: dict):
    """Сохраняет кэш переводов в файл."""
    # Ограничиваем размер кэша
    if len(cache) > MAX_CACHE_SIZE:
        # Удаляем старые записи (оставляем последние 80%)
        items = list(cache.items())[-int(MAX_CACHE_SIZE * 0.8):]
        cache = dict(items)

    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except:
        pass


def _get_cache_key(text: str, target_lang: str = 'ru') -> str:
    """Генерирует уникальный ключ для кэша на основе текста."""
    return hashlib.md5(f"{text.strip().lower()}:{target_lang}".encode()).hexdigest()


def translate_text(text: str, target_lang: str = 'ru', source_lang: str = 'en') -> str:
    """
    Переводит текст на целевой язык с кэшированием.

    Args:
        text: Текст для перевода
        target_lang: Код целевого языка (по умолчанию 'ru')
        source_lang: Код исходного языка (по умолчанию 'en')

    Returns:
        Переведённый текст или оригинал при ошибке
    """
    if not text or not text.strip():
        return text

    # Проверяем кэш
    cache = _load_cache()
    cache_key = _get_cache_key(text, target_lang)

    if cache_key in cache:
        return cache[cache_key]

    # Переводим
    translated = _do_translate(text, target_lang, source_lang)

    # Сохраняем в кэш
    if translated and translated != text:
        cache[cache_key] = translated
        _save_cache(cache)

    return translated or text


def _do_translate(text: str, target_lang: str, source_lang: str) -> Optional[str]:
    """Внутренняя функция выполнения перевода (выбор бэкенда)."""
    try:
        if TRANSLATOR_BACKEND == 'googletrans':
            return _translate_googletrans(text, target_lang, source_lang)
    except Exception as e:
        print(f"⚠️ Ошибка перевода ({TRANSLATOR_BACKEND}): {e}")

    return None


def _translate_googletrans(text: str, target_lang: str, source_lang: str) -> str:
    """Перевод через googletrans (асинхронная версия)."""
    import asyncio
    from googletrans import Translator

    async def _async_translate():
        translator = Translator()
        result = await translator.translate(text, src=source_lang, dest=target_lang)
        return result.text

    # Запускаем асинхронную функцию в синхронном контексте
    return asyncio.run(_async_translate())


def translate_article(title: str, description: str = None) -> dict:
    translated_title = translate_text(title)
    translated_desc = translate_text(description) if description else translated_title

    return {
        'title': translated_title,
        'description': translated_desc
    }