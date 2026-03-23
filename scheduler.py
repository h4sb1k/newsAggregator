# scheduler.py
import schedule
import time
import threading
from datetime import datetime, timedelta
from cnn_scraper import run_scraper
from db import clear_old_news, get_setting
from newsapi_parser import run_newsapiparser

# 🔄 Глобальная переменная для отслеживания последнего запуска
_last_run_timestamp = None
_COOLDOWN_SECONDS = 150  # 2.5 минуты — защита от дублей


def scheduled_job():
    """Задача для планировщика с учётом настроек."""
    global _last_run_timestamp

    # Проверяем, включено ли автообновление
    if get_setting('auto_update_enabled', 'true') != 'true':
        print("⏭️ Автообновление отключено в настройках")
        return

    now = datetime.now()

    # Проверка cooldown
    if _last_run_timestamp and (now - _last_run_timestamp).total_seconds() < 150:
        print(f"⏭️ Пропуск запуска: последний был {(now - _last_run_timestamp).seconds} сек назад")
        return

    _last_run_timestamp = now

    print(f"\n⏰ [{now.strftime('%H:%M:%S')}] 🚀 Запуск плановой задачи...")

    try:
        # Проверяем включение парсеров
        if get_setting('cnn_enabled', 'true') == 'true':
            run_scraper()

        if get_setting('parser_newsapi_enabled', 'true') == 'true':
            page_size = int(get_setting('newsapi_page_size', '10'))
            run_newsapiparser(page_size=page_size)

        # Очистка старых новостей
        cleanup_days = int(get_setting('cleanup_days', '7'))
        clear_old_news(days=cleanup_days)

        print("✅ Плановая задача завершена")
    except Exception as e:
        print(f"❌ Ошибка в scheduled_job: {e}")

def start_scheduler():
    """
    Настраивает и запускает планировщик в фоновом потоке.
    """
    print(f"\n{'=' * 60}")
    print("⏰ Scheduler initializing...")

    # 1. Настраиваем расписание
    schedule.every(3).hours.do(scheduled_job)
    schedule.every().day.at("00:00").do(scheduled_job)
    schedule.every().day.at("06:00").do(scheduled_job)
    schedule.every().day.at("12:00").do(scheduled_job)
    schedule.every().day.at("18:00").do(scheduled_job)

    # 2. 🔥 Запускаем СРАЗУ при старте приложения
    print("🔄 Running initial parse on startup...")
    scheduled_job()  # ← Раскомментируйте эту строку для немедленного запуска

    # 3. Функция бесконечного цикла планировщика
    def run_loop():
        print("🔁 Scheduler loop started")
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"⚠️ Error in scheduler loop: {e}")
            time.sleep(60)  # Проверка каждую минуту

    # 4. Запускаем цикл в отдельном потоке
    scheduler_thread = threading.Thread(target=run_loop, daemon=True)
    scheduler_thread.start()

    print("✅ Scheduler running in background thread")
    print(f"📅 Next runs: every 3 hours + daily at 00:00, 06:00, 12:00, 18:00")
    print(f"{'=' * 60}\n")