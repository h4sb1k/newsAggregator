# db.py
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
import bcrypt

DB_PATH = os.getenv('DB_PATH', 'news.db')

@contextmanager
def get_db_connection():
    """Контекстный менеджер для подключения к БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Инициализация всех таблиц."""
    with get_db_connection() as conn:
        # Таблица news
        conn.execute('''
                     CREATE TABLE IF NOT EXISTS news
                     (
                         id INTEGER PRIMARY KEY,
                         title TEXT NOT NULL,
                         description TEXT,
                         category TEXT DEFAULT 'International',
                         source TEXT NOT NULL,
                         date TEXT NOT NULL,
                         imageUrl TEXT,
                         url TEXT UNIQUE NOT NULL,
                         created_at TEXT DEFAULT CURRENT_TIMESTAMP
                     )
                     ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_date ON news(date DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_url ON news(url)')
        conn.commit()

    init_settings()
    init_users()


def insert_news(articles: list) -> int:
    """Вставляет новости в БД, пропуская дубликаты по URL."""
    inserted = 0
    with get_db_connection() as conn:
        for article in articles:
            try:
                conn.execute('''
                             INSERT
                             OR IGNORE INTO news 
                    (id, title, description, category, source, date, imageUrl, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                             ''', (
                                 article['id'],
                                 article['title'],
                                 article.get('description', article['title']),
                                 article.get('category', 'International'),
                                 article.get('source', 'CNN Lite'),
                                 article['date'],
                                 article.get('imageUrl', ''),
                                 article['url']
                             ))
                if conn.total_changes > 0:
                    inserted += 1
            except sqlite3.IntegrityError:
                continue
        conn.commit()
    return inserted


def get_news(limit: int = 50, category: str = None) -> list:
    """Получает новости из БД с фильтрацией."""
    with get_db_connection() as conn:
        if category and category.lower() != 'all':
            cursor = conn.execute('''
                                  SELECT *
                                  FROM news
                                  WHERE LOWER(category) = LOWER(?)
                                  ORDER BY date DESC
                                      LIMIT ?
                                  ''', (category, limit))
        else:
            cursor = conn.execute('''
                                  SELECT *
                                  FROM news
                                  ORDER BY date DESC
                                      LIMIT ?
                                  ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_all_news() -> list:
    """Получает все новости из БД."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM news ORDER BY date DESC')
        return [dict(row) for row in cursor.fetchall()]


def get_stats() -> dict:
    """Получает статистику."""
    with get_db_connection() as conn:
        total = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
        categories = conn.execute('''
                                  SELECT category, COUNT(*) as count
                                  FROM news
                                  GROUP BY category
                                  ''').fetchall()

        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_count = conn.execute('''
                                   SELECT COUNT(*)
                                   FROM news
                                   WHERE date LIKE ?
                                   ''', (f'{today}%',)).fetchone()[0]

    return {
        'total': total,
        'today': today_count,
        'by_category': {row['category']: row['count'] for row in categories}
    }


def clear_old_news(days: int = 7) -> int:
    """Удаляет старые новости и изображения."""
    # 🔧 ЛЕНИВЫЙ ИМПОРТ внутри функции
    from image_utils import delete_image

    deleted_count = 0
    with get_db_connection() as conn:
        cursor = conn.execute('''
                              SELECT imageUrl
                              FROM news
                              WHERE date < datetime('now', ?)
                              ''', (f'-{days} days',))

        images_to_delete = [
            row['imageUrl'] for row in cursor.fetchall()
            if row['imageUrl'] and row['imageUrl'].startswith('images/news/')
        ]

        conn.execute('''
                     DELETE
                     FROM news
                     WHERE date < datetime('now', ?)
                     ''', (f'-{days} days',))
        deleted_count = conn.total_changes
        conn.commit()

    for img_path in images_to_delete:
        delete_image(img_path)

    print(f"🗑️ Удалено {deleted_count} новостей и {len(images_to_delete)} изображений")
    return deleted_count


# ============================================
# НАСТРОЙКИ
# ============================================
def init_settings():
    """Создаёт таблицу настроек."""
    with get_db_connection() as conn:
        conn.execute('''
                     CREATE TABLE IF NOT EXISTS settings
                     (
                         key TEXT PRIMARY KEY,
                         value TEXT NOT NULL,
                         updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                     )
                     ''')

        defaults = {
            'auto_update_enabled': 'true',
            'auto_update_interval': '180',
            'parser_cnn_enabled': 'true',
            'parser_newsapi_enabled': 'true',
            'newsapi_page_size': '10',
            'cnn_enabled': 'true',
            'translation_enabled': 'true',
            'cleanup_days': '7'
        }

        for key, value in defaults.items():
            conn.execute('''
                         INSERT
                         OR IGNORE INTO settings (key, value) VALUES (?, ?)
                         ''', (key, value))
        conn.commit()


def get_setting(key: str, default: str = None) -> str:
    """Получает значение настройки."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def set_setting(key: str, value: str):
    """Устанавливает значение настройки."""
    with get_db_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        conn.commit()


def get_all_settings() -> dict:
    """Получает все настройки."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT key, value FROM settings')
        return {row['key']: row['value'] for row in cursor.fetchall()}


# ============================================
# ПОЛЬЗОВАТЕЛИ (АВТОРИЗАЦИЯ)
# ============================================
def init_users():
    """Создаёт таблицу пользователей и админа по умолчанию."""
    with get_db_connection() as conn:
        conn.execute('''
                     CREATE TABLE IF NOT EXISTS users
                     (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT UNIQUE NOT NULL,
                         password_hash TEXT NOT NULL,
                         email TEXT,
                         role TEXT DEFAULT 'admin',
                         is_active INTEGER DEFAULT 1,
                         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                         last_login TEXT,
                         failed_attempts INTEGER DEFAULT 0,
                         locked_until TEXT
                     )
                     ''')

        admin_exists = conn.execute(
            'SELECT id FROM users WHERE username = ?', ('admin',)
        ).fetchone()

        if not admin_exists:
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute('''
                         INSERT INTO users (username, password_hash, email, role)
                         VALUES (?, ?, ?, ?)
                         ''', ('admin', password_hash, 'admin@example.com', 'admin'))
            conn.commit()
            print("✅ Пользователь admin создан (пароль: admin123)")
            conn.execute('''INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?) ''', ('superAdmin123', password_hash, 'superAdmin123@example.com', 'SuperSecretPassword'))
            conn.commit()
        conn.commit()


def get_user_by_username(username: str) -> dict:
    """Получает пользователя по имени."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict:
    """Получает пользователя по ID."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def update_password(user_id: int, new_password: str):
    """Обновляет пароль пользователя."""
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with get_db_connection() as conn:
        conn.execute('''
                     UPDATE users
                     SET password_hash   = ?,
                         failed_attempts = 0,
                         locked_until    = NULL
                     WHERE id = ?
                     ''', (password_hash, user_id))
        conn.commit()


def record_login_attempt(username: str, success: bool):
    """Записывает попытку входа."""
    with get_db_connection() as conn:
        if success:
            conn.execute('''
                         UPDATE users
                         SET failed_attempts = 0,
                             locked_until    = NULL,
                             last_login      = CURRENT_TIMESTAMP
                         WHERE username = ?
                         ''', (username,))
        else:
            conn.execute('''
                         UPDATE users
                         SET failed_attempts = failed_attempts + 1,
                             locked_until    = datetime('now', '+15 minutes')
                         WHERE username = ?
                           AND failed_attempts < 5
                         ''', (username,))
        conn.commit()


def is_user_locked(username: str) -> bool:
    """
    Проверяет, заблокирован ли пользователь.
    🔧 ИСПРАВЛЕНО: совместимость с форматом дат SQLite
    """
    user = get_user_by_username(username)
    if not user:
        return False

    if user['locked_until']:
        try:
            # SQLite хранит даты как '2026-03-19 11:21:26' (с пробелом)
            # fromisoformat() ожидает '2026-03-19T11:21:26' (с T)
            lock_time_str = user['locked_until'].replace(' ', 'T')
            lock_time = datetime.fromisoformat(lock_time_str)

            if datetime.now() < lock_time:
                return True
            else:
                # Сбрасываем истёкшую блокировку
                with get_db_connection() as conn:
                    conn.execute('''
                                 UPDATE users
                                 SET locked_until    = NULL,
                                     failed_attempts = 0
                                 WHERE username = ?
                                 ''', (username,))
                    conn.commit()
        except (ValueError, TypeError) as e:
            # Если формат даты не распознан — считаем, что блокировка истекла
            print(f"⚠️ Ошибка парсинга даты блокировки: {e}")
            with get_db_connection() as conn:
                conn.execute('''
                             UPDATE users
                             SET locked_until    = NULL,
                                 failed_attempts = 0
                             WHERE username = ?
                             ''', (username,))
                conn.commit()

    return False