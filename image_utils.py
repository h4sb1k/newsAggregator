import os
import re
import hashlib
import requests
from pathlib import Path
from datetime import datetime
import aiohttp
import aiofiles


# Пути к папкам
STATIC_DIR = Path('static')
IMAGES_DIR = STATIC_DIR / 'images' / 'news'
PLACEHOLDER_PATH = 'images/news/placeholder.jpg'

# Создаём директорию при импорте
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

#Допустимые расширения и типы контента
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

#Таймауты
DOWNLOAD_TIMEOUT = 10
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^\w\-_.]', '_', filename)[:100]

def generate_image_filename(url: str, extension: str = '.jpg') -> str:
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"news_{url_hash}_{timestamp}{extension}"


def get_extension_from_url(url: str) -> str:
    parsed = url.split('?')[0]
    if '.' in parsed:
        ext = '.' + parsed.split('.')[-1].lower()
        if ext in ALLOWED_EXTENSIONS:
            return ext
    return '.jpg'


# image_utils.py — ключевые моменты

def download_image(url: str, news_id: int = None) -> str | None:
    """
    Синхронная загрузка изображения.
    Returns: '/news-image/filename.jpg' или None
    """
    if not url or url.strip() == '':
        return None

    url = url.strip()

    try:
        # Проверка кэша
        existing = find_existing_image(url)
        if existing:
            return existing

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=10, stream=True)
        if response.status_code != 200:
            return None

        content_type = response.headers.get('Content-Type', '').lower()
        if not any(mt in content_type for mt in ALLOWED_MIMETYPES):
            return None

        extension = get_extension_from_url(url)
        filename = generate_image_filename(url, extension)
        filepath = IMAGES_DIR / filename

        # Сохранение
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        if filepath.exists() and filepath.stat().st_size > 0:
            return f'/news-image/{filename}'  # ← Путь для эндпоинта Flask
        return None

    except Exception:
        return None

def find_existing_image(url: str) -> str | None:
    """Проверяет, есть ли уже скачанное изображение для этого URL."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
    pattern = f"news_{url_hash}_*"

    for filepath in IMAGES_DIR.glob(pattern):
        if filepath.suffix.lower() in ALLOWED_EXTENSIONS:
            return f'/news-image/{filepath.name}'
    return None


def delete_image(relative_path: str) -> bool:
    """Удаляет локальное изображение по относительному пути."""
    if not relative_path or relative_path == PLACEHOLDER_PATH:
        return False

    try:
        if relative_path.startswith('/news-image/'):
            filename = relative_path.replace('/news-image/', '')
            filepath = IMAGES_DIR / filename
        elif relative_path.startswith('images/news/'):
            filename = relative_path.replace('images/news/', '')
            filepath = IMAGES_DIR / filename
        else:
            filepath = Path(relative_path)

        if filepath.exists() and filepath.is_file():
            filepath.unlink()
            print(f"🗑️ Удалено: {filepath.name}")
            return True
    except Exception as e:
        print(f"⚠️ Ошибка удаления: {e}")

    return False


def cleanup_orphaned_images() -> int:
    from db import get_db_connection
    deleted_count = 0
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT imageUrl FROM news WHERE imageUrl IS NOT NULL AND imageUrl != ""')
        used_images = {row['imageUrl'] for row in cursor.fetchall()}

    for filepath in IMAGES_DIR.iterdir():
        if filepath.is_file() and filepath.suffix.lower() in ALLOWED_EXTENSIONS:
            relative_path = f'/news-image/{filepath.name}'
            if relative_path not in used_images:
                try:
                    filepath.unlink()
                    deleted_count += 1
                    print(f"🗑️ Удалено неиспользуемое: {filepath.name}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {filepath.name}: {e}")

    print(f"✅ Очистка завершена: удалено {deleted_count} изображений")
    return deleted_count


def ensure_placeholder():
    placeholder_path = STATIC_DIR / PLACEHOLDER_PATH
    if not placeholder_path.exists():
        import base64
        minimal_png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        )
        placeholder_path.parent.mkdir(parents=True, exist_ok=True)
        with open(placeholder_path, 'wb') as f:
            f.write(minimal_png)
        print(f"🖼️ Создан placeholder: {PLACEHOLDER_PATH}")