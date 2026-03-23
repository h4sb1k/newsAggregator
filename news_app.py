# news_app.py
from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length
from db import (
    init_db, get_all_news, get_stats, get_all_settings, get_setting, set_setting,
    get_user_by_username, verify_password, record_login_attempt, is_user_locked,
    get_user_by_id, update_password
)
from newsapi_parser import run_newsapiparser
from cnn_scraper import run_scraper
from scheduler import start_scheduler
import os, sys
import threading
from pathlib import Path
from functools import wraps
from datetime import timedelta

# НАСТРОЙКИ БЕЗОПАСНОСТИ
if getattr(sys, 'frozen', False):
    # PyInstaller: файлы рядом с exe
    _app_dir = Path(sys.executable).parent
    _template_folder = _app_dir / 'templates'
    _static_folder = _app_dir / 'static'
elif '__pypackages__' in sys.path or sys.argv[0].endswith('.pyz'):
    # Shiv .pyz: ресурсы внутри архива, данные рядом с .pyz
    _app_dir = Path(__file__).parent
    _data_dir = Path(sys.argv[0]).parent.resolve() if sys.argv[0].endswith('.pyz') else Path(__file__).parent
    _template_folder = _app_dir / 'templates'
    _static_folder = _app_dir / 'static'
    os.environ['DB_PATH'] = str(_data_dir / 'news.db')
else:
    # Обычный запуск из кода
    _template_folder = 'templates'
    _static_folder = 'static'

# Создаём папки для данных (если не существуют)
_data_dir = Path(os.getenv('DB_PATH', '.')).parent if 'DB_PATH' in os.environ else Path(__file__).parent
(_data_dir / 'static' / 'images' / 'news').mkdir(parents=True, exist_ok=True)

app = Flask(__name__,
            template_folder=str(_template_folder),
            static_folder=str(_static_folder),
            static_url_path='/static')

app.secret_key = os.getenv('SECRET_KEY', os.urandom(32).hex())
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Установите True при использовании HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# ИНИЦИАЛИЗАЦИЯ РАСШИРЕНИЙ
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Требуется авторизация'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["100 per hour", "20 per minute"],
    storage_uri="memory://"
)

@app.context_processor
def inject_user():
    """Делает current_user доступным во всех шаблонах."""
    return dict(current_user=current_user)

# ИНИЦИАЛИЗАЦИЯ БД И ПЛАНИРОВЩИКА
init_db()
start_scheduler()


# МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ (Flask-Login)
class User(UserMixin):
    def __init__(self, user_id, username, role='admin'):
        self.id = user_id
        self.username = username
        self.role = role

    def is_admin(self):
        return self.role == 'admin'


@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(int(user_id))
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'])
    return None


# ФОРМЫ (WTForms + CSRF)
class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6, max=128)])
    remember = BooleanField('Запомнить меня')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired()])


# ДЕКОРАТОРЫ БЕЗОПАСНОСТИ
def require_admin(f):
    """Требует авторизации и роли администратора."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
        if not current_user.is_admin():
            flash('Доступ запрещён. Требуется роль администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated


def require_ajax(f):
    """Требует AJAX-запрос (проверка заголовка)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # ✅ Проверка только по заголовку (is_xhr удалён в Flask 2.0+)
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return jsonify({'error': 'Invalid request type'}), 400
        return f(*args, **kwargs)
    return decorated

# ЭНДПОИНТ ДЛЯ ИЗОБРАЖЕНИЙ
@app.route('/news-image/<filename>')
@csrf.exempt  # Публичный доступ к картинкам
def serve_news_image(filename):
    """Раздача изображений новостей."""
    images_dir = Path('static') / 'images' / 'news'
    filepath = images_dir / filename

    if not filepath.exists():
        placeholder = images_dir / 'placeholder.jpg'
        if placeholder.exists():
            return send_from_directory(str(images_dir), 'placeholder.jpg')
        return "Image not found", 404

    return send_from_directory(
        str(images_dir),
        filename,
        max_age=86400,
        conditional=True
    )


# ПУБЛИЧНЫЕ МАРШРУТЫ
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news')
@csrf.exempt  # Публичный API
@limiter.limit("30 per minute")
def get_news_api():
    """Публичный API для получения новостей."""
    category = request.args.get('category', default=None)
    query = request.args.get('q', default='')
    limit = request.args.get('limit', default=None, type=int)

    from db import get_db_connection

    with get_db_connection() as conn:
        base_query = 'SELECT * FROM news WHERE 1=1'
        params = []

        if category and category.lower() != 'all':
            base_query += ' AND LOWER(category) = LOWER(?)'
            params.append(category)

        if query:
            base_query += ' AND (title LIKE ? OR description LIKE ?)'
            params.extend([f'%{query}%', f'%{query}%'])

        base_query += ' ORDER BY date DESC'
        if limit is not None:
            base_query += ' LIMIT ?'
            params.append(limit)

        cursor = conn.execute(base_query, params)
        news = [dict(row) for row in cursor.fetchall()]

    return jsonify(news)


@app.route('/api/stats')
@csrf.exempt
@limiter.limit("10 per minute")
def get_stats_api():
    """Публичная статистика."""
    stats = get_stats()
    return jsonify(stats)


@app.route('/api/parse', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per hour")
def trigger_parse():
    """Ручной запуск парсера (простая защита по токену)."""
    auth_token = request.headers.get('X-Auth-Token') or request.args.get('token')
    expected_token = os.getenv('PARSER_TOKEN', 'admin-secret-token')

    if auth_token != expected_token:
        return jsonify({'error': 'Unauthorized'}), 401

    page_size = request.args.get('page_size', default=10, type=int)
    page_size = max(1, min(page_size, 20))

    try:
        def run_in_thread():
            run_newsapiparser(page_size=page_size)

        thread = tahreading.Thread(target=run_in_thread)
        thread.start()
        return jsonify({'status': 'started', 'message': 'Parsing in background'})
    except Exception as e:
        print(f"❌ Parser error: {e}")
        return jsonify({'error': str(e)}), 500


# МАРШРУТЫ АВТОРИЗАЦИИ
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Страница входа."""
    if current_user.is_authenticated:
        return redirect(url_for('admin_panel'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        if is_user_locked(username):
            flash('Аккаунт временно заблокирован. Попробуйте через 15 минут.', 'error')
            return render_template('login.html', form=form)

        user_data = get_user_by_username(username)

        if user_data and verify_password(password, user_data['password_hash']):
            user = User(user_data['id'], user_data['username'], user_data['role'])
            login_user(user, remember=form.remember.data)
            record_login_attempt(username, success=True)

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('admin_panel'))
        else:
            record_login_attempt(username, success=False)
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """Выход из системы."""
    username = current_user.username
    logout_user()
    flash(f'Вы вышли из системы, {username}', 'info')
    return redirect(url_for('index'))

@app.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
@require_admin
def change_password():
    """Смена пароля администратора."""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        user_data = get_user_by_username(current_user.username)

        if not verify_password(form.current_password.data, user_data['password_hash']):
            flash('Неверный текущий пароль', 'error')
        elif form.new_password.data != form.confirm_password.data:
            flash('Пароли не совпадают', 'error')
        else:
            update_password(current_user.id, form.new_password.data)
            flash('Пароль успешно изменён', 'success')
            return redirect(url_for('admin_panel'))

    return render_template('change_password.html', form=form)


# ============================================
# ⚙️ АДМИН-ПАНЕЛЬ (ЗАЩИЩЕНА)
# ============================================
@app.route('/admin')
@login_required
@require_admin
def admin_panel():
    """Страница админ-панели."""
    return render_template('admin.html')


@app.route('/api/admin/settings', methods=['GET'])
@login_required
@require_admin
@require_ajax
@csrf.exempt
def api_get_settings():
    """Получение настроек (GET)."""
    settings = get_all_settings()
    return jsonify(settings)


@app.route('/api/admin/settings', methods=['POST'])
@login_required
@require_admin
@require_ajax
def api_update_settings():
    """Обновление настроек (POST с CSRF)."""
    csrf_token = request.headers.get('X-CSRFToken') or session.get('_csrf_token')
    if not csrf_token:
        return jsonify({'error': 'CSRF token missing'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    updated = []
    allowed_keys = [
        'auto_update_enabled', 'auto_update_interval',
        'parser_cnn_enabled', 'parser_newsapi_enabled',
        'newsapi_page_size', 'cnn_enabled',
        'translation_enabled', 'cleanup_days'
    ]

    for key, value in data.items():
        if key in allowed_keys:
            set_setting(key, str(value))
            updated.append(key)

    return jsonify({
        'success': True,
        'updated': updated,
        'message': f'Обновлено настроек: {len(updated)}'
    })


@app.route('/api/admin/parse', methods=['POST'])
@login_required
@require_admin
@require_ajax
def api_trigger_parse():
    """Запуск парсеров из админ-панели."""
    csrf_token = request.headers.get('X-CSRFToken') or session.get('_csrf_token')
    if not csrf_token:
        return jsonify({'error': 'CSRF token missing'}), 403

    data = request.get_json() or {}
    sources = data.get('sources', ['cnn', 'newsapi'])
    page_size = data.get('page_size', 10)

    results = {}

    def run_cnn():
        if get_setting('cnn_enabled', 'true') == 'true':
            try:
                count = run_scraper()
                results['cnn'] = {'success': True, 'inserted': count}
            except Exception as e:
                results['cnn'] = {'success': False, 'error': str(e)}

    def run_newsapi():
        if get_setting('parser_newsapi_enabled', 'true') == 'true':
            try:
                result = run_newsapiparser(page_size=page_size)
                results['newsapi'] = {'success': True, 'inserted': result.get('inserted', 0)}
            except Exception as e:
                results['newsapi'] = {'success': False, 'error': str(e)}

    threads = []
    if 'cnn' in sources and get_setting('cnn_enabled', 'true') == 'true':
        t = threading.Thread(target=run_cnn)
        t.start()
        threads.append(t)

    if 'newsapi' in sources and get_setting('parser_newsapi_enabled', 'true') == 'true':
        t = threading.Thread(target=run_newsapi)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return jsonify({
        'success': True,
        'results': results,
        'message': 'Парсинг завершён'
    })


@app.route('/api/admin/status')
@login_required
@require_admin
@require_ajax
@csrf.exempt
def api_admin_status():
    """Статус системы для админ-панели."""
    from db import get_db_connection

    with get_db_connection() as conn:
        total_news = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
        last_news = conn.execute('SELECT date FROM news ORDER BY date DESC LIMIT 1').fetchone()

    return jsonify({
        'total_news': total_news,
        'last_update': last_news['date'] if last_news else None,
        'auto_update_enabled': get_setting('auto_update_enabled', 'true') == 'true',
        'auto_update_interval': int(get_setting('auto_update_interval', '180')),
        'parsers': {
            'cnn': get_setting('cnn_enabled', 'true') == 'true',
            'newsapi': get_setting('parser_newsapi_enabled', 'true') == 'true'
        },
        'translation_enabled': get_setting('translation_enabled', 'true') == 'true',
        'current_user': current_user.username
    })


@app.route('/api/admin/logs')
@login_required
@require_admin
@require_ajax
@csrf.exempt
def api_admin_logs():
    """Последние 100 новостей для логов."""
    from db import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute('''
                              SELECT id, title, source, category, date, created_at
                              FROM news
                              ORDER BY created_at DESC
                                  LIMIT 100
                              ''')
        logs = [dict(row) for row in cursor.fetchall()]

    return jsonify(logs)


# ============================================
# ❌ ОБРАБОТЧИКИ ОШИБОК
# ============================================
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('index.html'), 404


@app.errorhandler(403)
def forbidden(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden'}), 403
    flash('Доступ запрещён', 'error')
    return redirect(url_for('login'))


@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Rate limit exceeded. Try again later.'}), 429
    flash('Слишком много запросов. Попробуйте позже.', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    flash('Произошла ошибка сервера', 'error')
    return render_template('index.html'), 500



# ============================================
# 🚀 ЗАПУСК СЕРВЕРА
# ============================================
def main():
    print("🚀 Starting Flask server on http://0.0.0.0:5000")
    print("🔐 Admin panel: http://localhost:5000/login")
    print("👤 Default credentials: admin / admin123")
    print("⚠️  CHANGE PASSWORD AFTER FIRST LOGIN!")
    print(f"🔑 SECRET_KEY: {app.secret_key[:16]}...")

    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)

if __name__ == '__main__':
    main()