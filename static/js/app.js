// static/js/app.js

// ============================================
// 🎨 УПРАВЛЕНИЕ ТЕМОЙ (функции определены ДО использования)
// ============================================
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

// Слушатель системной темы (работает всегда)
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (localStorage.getItem(THEME_KEY) === 'system') {
        applyTheme('system');
    }
});

// ============================================
// 📰 ОСНОВНОЙ КОД
// ============================================

// State
let allNews = [];
let filteredNews = [];
let currentCategory = 'all';
let displayedCount = 6;

// Категории
const ALL_CATEGORIES = [
    'Россия', 'США', 'Украина', 'Европа', 'Ближний Восток',
    'Азия', 'Северная Америка', 'Латинская Америка',
    'Африка', 'Австралия и Океания'
];

const categoryEmojis = {
    'Россия': '🇷🇺', 'США': '🇺🇸', 'Украина': '🇺🇦', 'Европа': '🇪🇺',
    'Ближний Восток': '🕌', 'Азия': '🌏', 'Северная Америка': '🌎',
    'Латинская Америка': '💃', 'Африка': '🌍', 'Австралия и Океания': '🦘',
    'International': '🌐', 'all': '📰'
};

// Initialize when DOM is ready — ЕДИНЫЙ обработчик!
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App initialized');

    // 🔘 Инициализация темы (теперь DOM уже загружен!)
    const savedTheme = localStorage.getItem(THEME_KEY) || 'system';
    applyTheme(savedTheme);
    updateThemeIcon(savedTheme);

    // Загрузка новостей
    loadNews();
    setupEventListeners();
    initCategoryCounts();

    // 🔘 Обработчик кнопки темы
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', openThemeModal);
    }

    // Закрытие модального окна по клику вне его
    document.getElementById('themeModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'themeModal') {
            closeThemeModal();
        }
    });

    // Закрытие по Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeThemeModal();
        }
    });
});

// Load news from API
async function loadNews() {
    try {
        console.log('📡 Fetching news from /api/news...');
        const response = await fetch('/api/news');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        allNews = await response.json();
        console.log(`✅ Loaded ${allNews.length} news articles`);

        filteredNews = [...allNews];
        updateCategoryCounts();
        updateStats();
        renderNews();
    } catch (error) {
        console.error('❌ Error loading news:', error);
        document.getElementById('newsGrid').innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">⚠️</div>
                <h3 class="empty-state-title">Ошибка загрузки</h3>
                <p class="empty-state-text">Проверьте подключение к серверу</p>
            </div>
        `;
    }
}

// Setup event listeners
function setupEventListeners() {
    document.querySelectorAll('.main-nav-item').forEach(btn => {
        btn.addEventListener('click', () => setCategory(btn.dataset.category));
    });

    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', () => setCategory(tab.dataset.category));
    });

    document.querySelectorAll('#sidebarCategories .category-item').forEach(item => {
        item.addEventListener('click', () => setCategory(item.dataset.category));
    });

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            filterNews(e.target.value);
        }, 300));
    }

    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            displayedCount += 6;
            renderNews();
        });
    }
}

function initCategoryCounts() {
    ALL_CATEGORIES.forEach(cat => {
        const el = document.getElementById(`count-${cat}`);
        if (el) el.textContent = '0';
    });
}

function setCategory(category) {
    console.log(`📂 Switching to category: ${category}`);
    currentCategory = category;
    displayedCount = 6;

    document.querySelectorAll('.main-nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });

    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.category === category);
    });

    document.querySelectorAll('#sidebarCategories .category-item').forEach(item => {
        item.classList.toggle('active', item.dataset.category === category);
    });

    filterNews(document.getElementById('searchInput')?.value || '');
}

function filterNews(searchQuery = '') {
    let news = [...allNews];

    if (currentCategory !== 'all') {
        const targetCategory = currentCategory.toLowerCase();
        news = news.filter(n => {
            const newsCategory = (n.category || '').toLowerCase();
            return newsCategory === targetCategory;
        });
    }

    if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        news = news.filter(n =>
            (n.title || '').toLowerCase().includes(query) ||
            (n.description || '').toLowerCase().includes(query) ||
            (n.source || '').toLowerCase().includes(query)
        );
    }

    news.sort((a, b) => new Date(b.date) - new Date(a.date));
    filteredNews = news;
    renderNews();
}

function renderNews() {
    const grid = document.getElementById('newsGrid');
    const loadMoreBtn = document.getElementById('loadMoreBtn');

    if (!grid) return;

    if (filteredNews.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">📰</div>
                <h3 class="empty-state-title">Ничего не найдено</h3>
                <p class="empty-state-text">Попробуйте изменить поисковый запрос или выбрать другую категорию</p>
            </div>
        `;
        if (loadMoreBtn) loadMoreBtn.disabled = true;
        return;
    }

    const visibleNews = filteredNews.slice(0, displayedCount);
    grid.innerHTML = visibleNews.map(news => createNewsCard(news)).join('');

    if (loadMoreBtn) {
        loadMoreBtn.disabled = displayedCount >= filteredNews.length;
        loadMoreBtn.style.display = displayedCount >= filteredNews.length ? 'none' : 'inline-block';
    }
}

function createNewsCard(news) {
    const category = news.category || 'International';
    const categoryKey = category.toLowerCase().replace(/[^a-zа-яё0-9]+/g, '-');
    const emoji = categoryEmojis[category] || categoryEmojis['International'];

    const date = new Date(news.date).toLocaleDateString('ru-RU', {
        day: 'numeric', month: 'long', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });

    const cssClass = `cat-${categoryKey}`;

    const imageUrl = news.imageUrl;
    const hasValidImage = imageUrl &&
                          !imageUrl.includes('placeholder') &&
                          imageUrl !== 'images/news/placeholder.jpg' &&
                          imageUrl !== '../placeholder.jpg';

    let imageSrc = null;
    if (hasValidImage) {
        if (imageUrl.startsWith('/news-image/')) {
            imageSrc = imageUrl;
        } else if (imageUrl.startsWith('images/news/')) {
            imageSrc = `static/${imageUrl}`;
        } else if (imageUrl.startsWith('http')) {
            imageSrc = imageUrl;
        } else {
            imageSrc = imageUrl;
        }
    }

    const imageBlock = hasValidImage && imageSrc
        ? `<img src="${imageSrc}" alt="" class="news-card-img" loading="lazy" onerror="this.parentElement.innerHTML='<span class=\\'placeholder-emoji\\'>${emoji}</span>'">`
        : `<span class="placeholder-emoji">${emoji}</span>`;

    return `
        <article class="news-card ${cssClass}" onclick="window.open('${escapeHtml(news.url || '#')}', '_blank')">
            <div class="news-card-image">${imageBlock}</div>
            <div class="news-card-content">
                <span class="news-card-category ${cssClass}">${emoji} ${escapeHtml(category)}</span>
                <h3 class="news-card-title">${escapeHtml(news.title || 'Без заголовка')}</h3>
                <p class="news-card-description">${escapeHtml(news.description || news.title || '')}</p>
                <div class="news-card-meta">
                    <span class="news-card-source">${escapeHtml(news.source || 'Unknown')}</span>
                    <span class="news-card-date">${date}</span>
                </div>
            </div>
        </article>
    `;
}

function updateCategoryCounts() {
    const allEl = document.getElementById('count-all');
    if (allEl) allEl.textContent = allNews.length;

    ALL_CATEGORIES.forEach(cat => {
        const count = allNews.filter(n => {
            const newsCat = (n.category || '').toLowerCase();
            return newsCat === cat.toLowerCase();
        }).length;
        const el = document.getElementById(`count-${cat}`);
        if (el) el.textContent = count;
    });
}

function updateStats() {
    const totalEl = document.getElementById('totalNews');
    const todayEl = document.getElementById('todayNews');

    if (totalEl) totalEl.textContent = allNews.length;

    if (todayEl) {
        const today = new Date().toDateString();
        const todayCount = allNews.filter(n => {
            try {
                return new Date(n.date).toDateString() === today;
            } catch { return false; }
        }).length;
        todayEl.textContent = todayCount;
    }
}

function showInfo(type) {
    const messages = {
        'about': 'Агрегатор Новостей "МАЯК" \n\nВерсия: 1.0.0',
    };
    alert(messages[type] || 'Информация недоступна');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}
// Открытие модального окна подтверждения выхода
function confirmLogout() {
    const modal = document.getElementById('logoutModal');
    if (modal) {
        modal.classList.add('active');
    }
}

// Закрытие модального окна
function closeLogoutModal() {
    const modal = document.getElementById('logoutModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Закрытие по клику вне окна
document.getElementById('logoutModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'logoutModal') {
        closeLogoutModal();
    }
});

// Закрытие по Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeLogoutModal();
    }
});