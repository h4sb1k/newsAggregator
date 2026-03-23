# newsapi_parser.py
"""
Парсер для NewsAPI с многопоточной загрузкой для высокой скорости.
Запуск: python newsapi_parser.py
"""
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from newsapi import NewsApiClient
from classifier import classify_articles
from db import init_db, insert_news
from image_utils import download_image, PLACEHOLDER_PATH

# 🔐 API-ключ
API_KEY = os.getenv('NEWSAPI_KEY', '90b69fd7887e4e4993b0516d5ba0b546')
newsapi = NewsApiClient(api_key=API_KEY)

# ⚙️ НАСТРОЙКИ ПРОИЗВОДИТЕЛЬНОСТИ
MAX_WORKERS_REGIONS = 3  # Сколько регионов парсить параллельно
MAX_WORKERS_IMAGES = 5  # Сколько картинок качать параллельно
REQUEST_TIMEOUT = 15  # Таймаут запроса в секундах

# 🌍 Конфигурация регионов
REGION_CONFIGS = {
    'Россия': {
        'q': 'Россия OR Путин OR Москва OR Кремль OR РФ',
        'language': 'ru',
        'sort_by': 'publishedAt',
        'domains': 'ria.ru,rt.com,tass.ru,interfax.ru,lenta.ru'
    },
    'США': {
        'q': 'США OR Америка OR Байден OR Трамп OR Вашингтон',
        'language': 'ru',
        'sort_by': 'publishedAt'
    },
    'Украина': {
        'q': 'Украина OR Зеленский OR Киев',
        'language': 'ru',
        'sort_by': 'publishedAt'
    },
    'Европа': {
        'q': 'Европа OR ЕС OR Германия OR Франция',
        'language': 'ru',
        'sort_by': 'publishedAt'
    },
    'Ближний Восток': {
        'q': 'Ближний Восток OR Израиль OR Иран',
        'language': 'ru',
        'sort_by': 'publishedAt'
    },
    'Азия': {
        'q': 'Азия OR Китай OR Япония OR Индия',
        'language': 'ru',
        'sort_by': 'publishedAt'
    },
    'Африка': {'q': 'Африка', 'language': 'ru', 'sort_by': 'publishedAt'},
    'Латинская Америка': {'q': 'Латинская Америка', 'language': 'ru', 'sort_by': 'publishedAt'},
    'Северная Америка': {'q': 'Канада', 'language': 'ru', 'sort_by': 'publishedAt'},
    'Австралия и Океания': {'q': 'Австралия', 'language': 'ru', 'sort_by': 'publishedAt'}
}

FALLBACK_CONFIGS = {
    'Африка': {'q': 'Africa', 'language': 'en', 'sort_by': 'publishedAt'},
    'Латинская Америка': {'q': 'Latin America', 'language': 'en', 'sort_by': 'publishedAt'},
    'Австралия и Океания': {'q': 'Australia', 'language': 'en', 'sort_by': 'publishedAt'}
}


def fetch_region_news_sync(region_name: str, page_size: int = 15) -> list:
    """
    Синхронная функция получения новостей для одного региона.
    """
    config = REGION_CONFIGS.get(region_name)
    if not config:
        return []

    articles = []
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')

    try:
        # 🔹 Попытка 1: русский язык
        response = newsapi.get_everything(
            q=config['q'],
            language=config.get('language', 'ru'),
            from_param=from_date,
            sort_by=config.get('sort_by', 'publishedAt'),
            page_size=page_size,
            page=1,
            domains=config.get('domains')
        )

        if response.get('status') == 'ok' and response['articles']:
            articles = _parse_articles_sync(response['articles'], region_name)
            print(f"✅ {region_name} [ru]: {len(articles)} статей")
            return articles

    except Exception as e:
        print(f"⚠️ Ошибка [ru, {region_name}]: {e}")

    # 🔹 Попытка 2: английский fallback (если нужно)
    if len(articles) < page_size // 2 and region_name in FALLBACK_CONFIGS:
        try:
            fb_config = FALLBACK_CONFIGS[region_name]
            response = newsapi.get_everything(
                q=fb_config['q'],
                language=fb_config['language'],
                from_param=from_date,
                sort_by=fb_config['sort_by'],
                page_size=page_size - len(articles),
                page=1
            )
            if response.get('status') == 'ok':
                fb_articles = _parse_articles_sync(response['articles'], region_name)
                articles.extend(fb_articles)
                print(f"✅ {region_name} [en fallback]: +{len(fb_articles)}")
        except Exception as e:
            print(f"⚠️ Ошибка [en fallback, {region_name}]: {e}")

    return articles


def _parse_articles_sync(articles_list: list, region_name: str) -> list:
    """
    Парсит статьи и загружает изображения параллельно (через ThreadPool).
    """
    parsed = []

    # 1. Подготавливаем данные и задачи для картинок
    tasks = []
    for article in articles_list:
        if not article.get('title') or article['title'] == '[Removed]':
            continue

        url_hash = abs(hash(article['url'])) % 1_000_000_000
        image_url = article.get('urlToImage')

        tasks.append({
            'article': article,
            'url_hash': url_hash,
            'image_url': image_url.strip() if image_url else None
        })

    # 2. Параллельно скачиваем изображения
    print(f"📥 Загрузка {len(tasks)} изображений для {region_name}...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_IMAGES) as executor:
        # Создаём будущие (futures) для всех задач
        future_to_task = {
            executor.submit(download_image, t['image_url']): t
            for t in tasks if t['image_url']
        }

        # Словарь результатов: url_hash -> local_path
        image_results = {}

        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                image_results[task['url_hash']] = result or PLACEHOLDER_PATH
            except Exception:
                image_results[task['url_hash']] = PLACEHOLDER_PATH

    # 3. Формируем финальный список статей
    for task in tasks:
        local_image_path = image_results.get(task['url_hash'], PLACEHOLDER_PATH)

        parsed.append({
            'id': task['url_hash'],
            'title': task['article']['title'],
            'description': task['article'].get('description') or task['article']['title'],
            'source': task['article']['source'].get('name', 'Unknown'),
            'date': task['article']['publishedAt'],
            'imageUrl': local_image_path,
            'url': task['article']['url'],
            'category': region_name
        })

    return parsed


def parse_all_regions_sync(page_size: int = 12) -> list:
    """
    Собирает новости со всех регионов параллельно.
    """
    print(f"🌍 Сбор новостей: {len(REGION_CONFIGS)} регионов (параллельно ×{MAX_WORKERS_REGIONS})")

    all_articles = []

    # Запускаем регионы параллельно через ThreadPool
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_REGIONS) as executor:
        # Создаём задачи
        future_to_region = {
            executor.submit(fetch_region_news_sync, region_name, page_size): region_name
            for region_name in REGION_CONFIGS.keys()
        }

        # Собираем результаты по мере готовности
        for future in as_completed(future_to_region):
            region_name = future_to_region[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                print(f"❌ Ошибка в регионе {region_name}: {e}")

    print(f"📦 Всего собрано: {len(all_articles)} статей")
    return all_articles


def run_newsapiparser(page_size: int = 12) -> dict:
    """Полный цикл парсинга."""
    print(f"\n{'=' * 60}")
    print(f"🔄 NewsAPI Parser [Multi-threaded] — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'=' * 60}")

    start_time = datetime.now()

    init_db()

    # 1. Сбор новостей (параллельно)
    raw_articles = parse_all_regions_sync(page_size)

    if not raw_articles:
        print("❌ Не удалось получить новости")
        return {'error': 'No articles fetched', 'inserted': 0}

    # 2. Классификация
    print(f"🔍 Классификация {len(raw_articles)} статей...")
    classified_articles = classify_articles(raw_articles)

    # 3. Сохранение в БД
    print("💾 Сохранение в БД...")
    inserted_count = insert_news(classified_articles)

    # 4. Статистика
    category_stats = {}
    for article in classified_articles:
        cat = article.get('category', 'International')
        category_stats[cat] = category_stats.get(cat, 0) + 1

    elapsed = (datetime.now() - start_time).total_seconds()

    result = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'fetched': len(classified_articles),
        'inserted': inserted_count,
        'by_category': category_stats,
        'elapsed_seconds': round(elapsed, 1)
    }

    print(f"\n⏱️ Затрачено времени: {elapsed:.1f} сек")
    print(f"✅ Обработано: {result['fetched']}, Добавлено: {result['inserted']}")
    print("📊 Категории:")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"   • {cat}: {count}")
    print(f"{'=' * 60}\n")

    return result


if __name__ == '__main__':
    run_newsapiparser(page_size=10)