import logging
import os
import re
import datetime
import pytz

from threading import Thread
from flask import Flask

# ⭐️ НОВЫЕ БИБЛИОТЕКИ ДЛЯ БАЗЫ ДАННЫХ
from upstash_redis import Redis

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters, JobQueue
from telegram.constants import ParseMode

# --- Настройки бота (ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ) ---
TOKEN = os.environ.get('TOKEN')
# ⭐️ НОВЫЕ КЛЮЧИ ИЗ UPSTASH (Акт I)
UPSTASH_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')

# ⭐️ НОВОЕ: Подключение к Базе Данных (Redis)
try:
    redis = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
    logger = logging.getLogger(__name__) # Определяем logger здесь
    logger.info("Успешное подключение к Upstash (Redis)!")
except Exception as e:
    # Если логгер еще не создан, просто выводим в print
    print(f"Критическая ошибка: Не удалось подключиться к Upstash (Redis)! {e}")
    exit()

# --- Веб-сервер (Для UptimeRobot) ---
app = Flask('')
@app.route('/')
def home():
    return "Бот 'ПОТУЖНИЙ' активний!"

def run_web_server():
    # Render.com сам найдет этот порт
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
# ------------------------------------

# --- Логика самого бота ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- ⭐️ ОБНОВЛЕНО: Функции для работы с БД (Redis) ---
# Мы будем использовать "Hash" (Словарь) в Redis под названием 'potuzhniy_scores'
SCORES_KEY = "potuzhniy_scores"

def load_scores(chat_id):
    """Загружает очки для ОДНОГО чата из БД Redis."""
    try:
        score = redis.hget(SCORES_KEY, chat_id)
        if score is None:
            return 0
        return int(score)
    except Exception as e:
        logger.error(f"Ошибка чтения из Redis для chat_id {chat_id}: {e}")
        return 0

def save_scores(chat_id, new_score):
    """Сохраняет очки для ОДНОГО чата в БД Redis."""
    try:
        redis.hset(SCORES_KEY, chat_id, new_score)
    except Exception as e:
        logger.error(f"Ошибка записи в Redis для chat_id {chat_id}: {e}")

# --- ⭐️ Ежедневное сообщение ---
async def send_evening_message(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Запуск щоденного завдання: вечірнє повідомлення...")
    try:
        all_chats = redis.hgetall(SCORES_KEY)
        if not all_chats:
            logger.info("Не знайдено чатів у БД (Redis), повідомлення пропущено.")
            return

        for chat_id in all_chats.keys():
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Добрий вечір ,як у всіх з ПОТУЖНІСТЮ ?"
                )
                logger.info(f"Надіслано вечірнє повідомлення до чату: {chat_id}")
            except Exception as e:
                logger.warning(f"Не вдалося надіслати повідомлення до {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка получения списка чатов из Redis для рассылки: {e}")


# --- ⭐️⭐️⭐️ ПОЛНОСТЬЮ НОВЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ⭐️⭐️⭐️ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
        
    message_text = update.message.text.strip()
    chat_id = str(update.message.chat_id) 

    # --- Ссылки на GIF (взяты из твоих сообщений) ---
    GIF_PLUS = "https://tenor.com/fc9tON9DdOq.gif"
    GIF_MINUS = "https://tenor.com/eRs2gXpleGo.gif"
    GIF_300 = "https://tenor.com/ZDv9rJSjG3.gif"
    GIF_OVER_1000 = "https://tenor.com/oIcXSh7dq8S.gif"
    # Это PNG, будем отправлять как ФОТО
    PNG_OVER_10 = "https://media.tenor.com/y33L_hgPoYsAAAAe/%D0%BF%D0%BE%D1%82%D1%83%D0%B6%D0%BD%D0%BE-%D0%BD%D0%B5-%D0%BF%D0%BE%D1%82%D1%83%D0%B6%D0%BD%D0%BE.png"

    # re.search() ищет В ЛЮБОМ МЕСТЕ СООБЩЕНИЯ (вместо re.match())
    match = re.search(r'([+-])\s*(\d+)', message_text)

    if not match:
        return # Ничего не найдено, выходим

    try:
        operator = match.group(1) # '+' или '-'
        value = int(match.group(2)) # Число
    except (ValueError, IndexError):
        return # Ошибка в regex (не должно случиться)

    # --- ⭐️ НОВАЯ ЛОГИКА ПРОВЕРОК ---
    
    # 1. Проверяем ПЛЮСЫ
    if operator == '+':
        if value == 300:
            await update.message.reply_animation(GIF_300)
            return # Очки не считаем
            
        if value > 1000:
            await update.message.reply_animation(GIF_OVER_1000)
            return # Очки не считаем
            
        if value > 10:
            # Отправляем PNG как ФОТО
            await update.message.reply_photo(PNG_OVER_10) 
            return # Очки не считаем
        
        # Если value <= 10 (все проверки пройдены)
        current_score = load_scores(chat_id)
        new_score = current_score + value
        save_scores(chat_id, new_score)
        
        await update.message.reply_animation(
            animation=GIF_PLUS,
            caption=f"🏆 <b>Рахунок потужності:</b> <code>{new_score}</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Проверяем МИНУСЫ
    if operator == '-':
        if value > 1000:
            await update.message.reply_animation(GIF_OVER_1000)
            return # Очки не считаем
            
        if value > 10:
            await update.message.reply_photo(PNG_OVER_10)
            return # Очки не считаем
        
        # Если value <= 10 (все проверки пройдены)
        current_score = load_scores(chat_id)
        new_score = current_score - value
        save_scores(chat_id, new_score)
        
        await update.message.reply_animation(
            animation=GIF_MINUS,
            caption=f"🏆 <b>Рахунок потужності:</b> <code>{new_score}</code>",
            parse_mode=ParseMode.HTML
        )
        return

# --- Функция запуска бота ---
def main_bot():
    job_queue = JobQueue()
    application = Application.builder().token(TOKEN).job_queue(job_queue).build()

    UKRAINE_TZ = pytz.timezone('Europe/Kyiv')
    job_time = datetime.time(hour=20, minute=0, tzinfo=UKRAINE_TZ)
    
    job_queue.run_daily(
        send_evening_message,
        time=job_time,
        days=(0, 1, 2, 3, 4, 5, 6)
    )
    logger.info("Заплановано щоденне повідомлення на 20:00 (Europe/Kyiv).")

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Бот 'ПОТУЖНИЙ' запущен...")
    application.run_polling()

# --- Главный запуск (Бота и Веб-сервера) ---
if __name__ == '__main__':
    if not TOKEN or not UPSTASH_URL or not UPSTASH_TOKEN:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют TOKEN, UPSTASH_URL или UPSTASH_TOKEN!")
    else:
        print("Запуск веб-сервера для UptimeRobot...")
        server_thread = Thread(target=run_web_server)
        server_thread.daemon = True 
        server_thread.start()

        main_bot()
