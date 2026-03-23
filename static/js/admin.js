
// 🎨 Управление темой (ТАКОЙ ЖЕ как на index.html)
const THEME_KEY = 'news_app_theme';

function applyTheme(theme) {
    if (theme === 'system') {
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', systemTheme);
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('.theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '🌙' : theme === 'light' ? '☀️' : '🌗';
    }
}

function updateThemeModal(theme) {
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.toggle('active', option.dataset.theme === theme);
    });
}

function setTheme(theme) {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    updateThemeIcon(theme);
    updateThemeModal(theme);
    closeThemeModal();
}

function openThemeModal() {
    const modal = document.getElementById('themeModal');
    if (modal) {
        updateThemeModal(localStorage.getItem(THEME_KEY) || 'system');
        modal.classList.add('active');
    }
}

function closeThemeModal() {
    const modal = document.getElementById('themeModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (localStorage.getItem(THEME_KEY) === 'system') {
        applyTheme('system');
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem(THEME_KEY) || 'system';
    applyTheme(savedTheme);
    updateThemeIcon(savedTheme);

    document.getElementById('themeToggle')?.addEventListener('click', openThemeModal);

    document.getElementById('themeModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'themeModal') closeThemeModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeThemeModal();
    });
});

// ============================================
// 🔐 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

function checkAuthResponse(response) {
    if (response.status === 401) {
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
        return false;
    }
    if (response.status === 403) {
        alert('Доступ запрещён');
        return false;
    }
    return true;
}

function confirmLogout() {
    const modal = document.getElementById('logoutModal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeLogoutModal() {
    const modal = document.getElementById('logoutModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

document.getElementById('logoutModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'logoutModal') {
        closeLogoutModal();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeLogoutModal();
    }
});

function showSaveStatus(message, type = 'info') {
    const status = document.getElementById('saveStatus');
    if (!status) return;

    status.textContent = message;
    status.className = 'save-status ' + (type === 'success' ? 'success' : type === 'error' ? 'error' : '');

    if (type !== 'error') {
        setTimeout(() => {
            if (status.textContent === message) {
                status.textContent = '';
            }
        }, 3000);
    }
}

// ============================================
// 📊 Загрузка статуса системы
// ============================================
async function loadStatus() {
    try {
        const response = await fetch('/api/admin/status', {
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });

        if (!checkAuthResponse(response)) return;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const status = await response.json();

        document.getElementById('totalNews').textContent = status.total_news || 0;
        document.getElementById('lastUpdate').textContent = status.last_update
            ? new Date(status.last_update).toLocaleString('ru-RU')
            : '-';

        const autoUpdate = status.auto_update_enabled;
        const indicator = document.getElementById('autoUpdateStatus');
        const text = document.getElementById('autoUpdateText');

        if (autoUpdate) {
            indicator.className = 'status-indicator status-active';
            text.textContent = 'Включено';
        } else {
            indicator.className = 'status-indicator status-inactive';
            text.textContent = 'Выключено';
        }

    } catch (error) {
        console.error('❌ Ошибка загрузки статуса:', error);
        document.getElementById('lastUpdate').textContent = 'Ошибка';
    }
}

// ============================================
// ⚙️ Загрузка настроек
// ============================================
async function loadSettings() {
    try {
        const response = await fetch('/api/admin/settings', {
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });

        if (!checkAuthResponse(response)) return;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const settings = await response.json();

        document.querySelectorAll('[data-setting]').forEach(el => {
            const key = el.dataset.setting;
            const value = settings[key];

            if (el.type === 'checkbox') {
                el.checked = value === 'true';
            } else if (el.type === 'number' || el.type === 'text') {
                el.value = value || el.defaultValue || '';
            }
        });

        console.log('✅ Настройки загружены:', settings);

    } catch (error) {
        console.error('❌ Ошибка загрузки настроек:', error);
        showSaveStatus('Ошибка загрузки настроек', 'error');
    }
}

// ============================================
// 💾 Сохранение всех настроек одним запросом
// ============================================
async function saveAllSettings() {
    const btn = document.getElementById('saveSettingsBtn');

    btn.disabled = true;
    btn.textContent = '⏳ Сохранение...';

    try {
        const settings = {};
        document.querySelectorAll('[data-setting]').forEach(el => {
            const key = el.dataset.setting;

            if (el.type === 'checkbox') {
                settings[key] = el.checked ? 'true' : 'false';
            } else if (el.type === 'number') {
                settings[key] = String(parseInt(el.value) || 0);
            } else {
                settings[key] = String(el.value || '').trim();
            }
        });

        const response = await fetch('/api/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(settings),
            credentials: 'same-origin'
        });

        if (!checkAuthResponse(response)) {
            btn.disabled = false;
            btn.textContent = '💾 Сохранить настройки';
            return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();

        showSaveStatus('✓ Настройки сохранены!', 'success');

        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = '💾 Сохранить настройки';
        }, 2000);

    } catch (error) {
        console.error('❌ Ошибка сохранения:', error);
        showSaveStatus('❌ Ошибка сохранения', 'error');
        btn.disabled = false;
        btn.textContent = '💾 Сохранить настройки';
    }
}

// ============================================
// 🔄 Запуск парсеров
// ============================================
async function runParse(sources) {
    const progressContainer = document.getElementById('progressContainer');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    progressContainer.style.display = 'block';
    progressFill.style.width = '20%';
    progressText.textContent = 'Подключение...';

    try {
        const response = await fetch('/api/admin/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                sources: sources,
                page_size: parseInt(document.getElementById('newsapiPageSize').value)
            }),
            credentials: 'same-origin'
        });

        if (!checkAuthResponse(response)) {
            progressContainer.style.display = 'none';
            return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        progressFill.style.width = '60%';
        progressText.textContent = 'Обработка...';

        const result = await response.json();

        progressFill.style.width = '100%';
        progressText.textContent = '✅ Готово!';

        setTimeout(() => {
            loadStatus();
            loadLogs();
            progressContainer.style.display = 'none';
        }, 2000);

    } catch (error) {
        console.error('❌ Ошибка парсинга:', error);
        progressFill.style.width = '100%';
        progressText.textContent = '❌ Ошибка!';
        alert('Ошибка при обновлении новостей!');
    }
}

// ============================================
// 📋 Загрузка логов
// ============================================
async function loadLogs() {
    const tbody = document.getElementById('logsTableBody');

    try {
        const response = await fetch('/api/admin/logs', {
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });

        if (!checkAuthResponse(response)) return;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const logs = await response.json();

        if (!Array.isArray(logs) || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Нет новостей</td></tr>';
            return;
        }

        tbody.innerHTML = logs.map(log => {
            const date = log.date ? new Date(log.date).toLocaleString('ru-RU', {
                day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
            }) : '-';

            const title = log.title
                ? (log.title.length > 50 ? log.title.substring(0, 50) + '...' : log.title)
                : 'Без заголовка';

            return `
                <tr>
                    <td>${log.id || '-'}</td>
                    <td title="${escapeHtml(log.title || '')}">${escapeHtml(title)}</td>
                    <td>${escapeHtml(log.source || '-')}</td>
                    <td>${escapeHtml(log.category || '-')}</td>
                    <td>${date}</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error('❌ Ошибка загрузки логов:', error);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#ef4444">Ошибка загрузки</td></tr>`;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// 🚀 Инициализация
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔧 Admin panel initialized');

    loadSettings();
    loadStatus();
    loadLogs();

    setInterval(loadStatus, 30000);
    setInterval(loadLogs, 60000);
});

