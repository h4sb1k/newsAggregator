# cnn_scraper.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from classifier import classify_articles
from db import init_db, insert_news
from translator import translate_article  # ← Импорт переводчика

# 🔧 Настройки
ENABLE_TRANSLATION = True  # Включить перевод для не-русских новостей
TRANSLATE_ONLY_IF_NEEDED = True  # Переводить только если текст не на русском


def is_russian_text(text: str) -> bool:
    """Проверяет, содержит ли текст русские буквы."""
    if not text:
        return False
    # Проверяем наличие кириллицы
    return bool(any('\u0400' <= char <= '\u04FF' for char in text))


def parse_cnn_lite():
    """Parses the CNN Lite website to extract latest news stories."""
    url = "https://lite.cnn.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching the page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = []

    for link in soup.find_all('a', href=True):
        parent_li = link.find_parent('li', class_='card--lite')
        if not parent_li:
            continue

        title = link.get_text(strip=True)
        relative_url = link.get('href', '').strip()

        if not title or not relative_url:
            continue

        # Формируем полный URL
        if relative_url.startswith('/'):
            full_url = f"https://lite.cnn.com{relative_url}"
        elif relative_url.startswith('http'):
            full_url = relative_url
        else:
            full_url = f"https://lite.cnn.com/{relative_url}"

        # 🔍 Пытаемся найти изображение
        image_url = None
        img_tag = parent_li.find('img')
        if img_tag and img_tag.get('src'):
            img_src = img_tag['src']
            if img_src.startswith('http'):
                image_url = img_src
            elif img_src.startswith('//'):
                image_url = f'https:{img_src}'
            elif img_src.startswith('/'):
                image_url = f'https://lite.cnn.com{img_src}'

        from image_utils import download_image, PLACEHOLDER_PATH
        local_image_path = download_image(image_url) if image_url else None
        if not local_image_path:
            local_image_path = PLACEHOLDER_PATH

        unique_id = abs(hash(full_url)) % (10 ** 8)

        # 🔄 Перевод заголовка и описания (если нужно)
        if ENABLE_TRANSLATION:
            if not TRANSLATE_ONLY_IF_NEEDED or not is_russian_text(title):
                translated = translate_article(title, title)  # description = title для CNN
                final_title = translated['title']
                final_description = translated['description']
                print(f"🌐 Переведено: '{title[:50]}...' → '{final_title[:50]}...'")
            else:
                final_title = title
                final_description = title
        else:
            final_title = title
            final_description = title

        article = {
            "id": unique_id,
            "title": final_title,  # ← Переведённый или оригинальный
            "description": final_description,
            "category": "International",  # Будет переопределено классификатором
            "source": "CNN Lite",
            "date": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "imageUrl": local_image_path,
            "url": full_url
        }
        articles.append(article)

    return articles


def run_scraper():
    """Запускает полный цикл парсинга, классификации и сохранения."""
    print(f"\n{'=' * 60}")
    print(f"🔄 CNN Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    init_db()

    print("🕷️  Parsing CNN Lite...")
    parsed_news = parse_cnn_lite()

    if not parsed_news:
        print("❌ No news articles were parsed.")
        return 0

    print(f"🏷️  Classifying {len(parsed_news)} articles...")
    classified_news = classify_articles(parsed_news)

    print("💾 Saving to database...")
    inserted = insert_news(classified_news)

    category_stats = {}
    for article in classified_news:
        cat = article['category']
        category_stats[cat] = category_stats.get(cat, 0) + 1

    print(f"\n✅ Processed: {len(parsed_news)}, Inserted: {inserted}")
    print("📊 Categories:")
    for cat, count in sorted(category_stats.items()):
        print(f"   • {cat}: {count}")
    print(f"{'=' * 60}\n")

    return inserted


if __name__ == "__main__":
    run_scraper()