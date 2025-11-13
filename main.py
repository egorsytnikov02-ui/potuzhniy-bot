import logging
import os
import re
import datetime
import pytz
import asyncio # 👈 Нужно для веб-хука

from flask import Flask, request # 👈 'request' - это новое

# ⭐️ НОВЫЕ БИБЛИОТЕКИ ДЛЯ БАЗЫ ДАННЫХ
from upstash_redis import Redis

from telegram import Update
# ⭐️ 'Bot' - это новое
from telegram.ext import Application, MessageHandler, ContextTypes, filters, JobQueue, Bot
from telegram.constants import ParseMode

# --- Настройки бота (ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ) ---
TOKEN = os.environ.get('TOKEN')
UPSTASH_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
# ⭐️ НОВЫЙ КЛЮЧ: URL нашего хостинга
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL') # Render сам даст нам этот ключ

# ⭐️ НОВОЕ: Подключение к Базе Данных (Redis)
try:
    redis = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
    logger = logging.getLogger(__name__) # Определяем logger здесь
    logger.info("Успешное подключение к Upstash (Redis)!")
except Exception as e:
    # Если логгер еще не создан, просто выводим в print
    print(f"Критическая ошибка: Не удалось подключиться к Upstash (Redis)! {e}")
    exit()

# --- Логика самого бота ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- ⭐️ Функции для работы с БД (Redis) - БЕЗ ИЗМЕНЕНИЙ ---
SCORES_KEY = "potuzhniy_scores"

def load_scores(chat_id):
    try:
        score = redis.hget(SCORES_KEY, chat_id)
        if score is None: return 0
        return int(score)
    except Exception as e:
        logger.error(f"Ошибка чтения из Redis для chat_id {chat_id}: {e}")
        return 0

def save_scores(chat_id, new_score):
    try:
        redis.hset(SCORES_KEY, chat_id, new_score)
    except Exception as e:
        logger.error(f"Ошибка записи в Redis для chat_id {chat_id}: {e}")

# --- ⭐️ Ежедневное сообщение ---
# (Эта функция остается, но запускать ее будет JobQueue)
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

# --- ⭐️ Обработчик сообщений (С GIF-ками) - БЕЗ ИЗМЕНЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    message_text = update.message.text.strip()
    chat_id = str(update.message.chat_id) 

    GIF_PLUS = "https://media.tenor.com/1-qF1-5K2wYAAAAj/potuzhno-power.gif"
    GIF_MINUS = "https://media.tenor.com/G5g2_d5d0w8AAAAj/potuzhno-unpowerful.gif"
    GIF_300 = "https://media.tenor.com/y1vOsdP-n7sAAAAj/potuzhno.gif"
    GIF_OVER_1000 = "https://media.tenor.com/Q2-F-QJp-YcAAAAj/shef-go-to-hell.gif"
    PNG_OVER_10 = "https://media.tenor.com/y33L_hgPoYsAAAAe/%D0%BF%D0%BE%D1%82%D1%83%D0%B6%D0%BD%D0%BE-%D0%BD%D0%B5-%D0%BF%D0%BE%D1%82%D1%83%D0%B6%D0%BD%D0%BE.png"

    match = re.search(r'([+-])\s*(\d+)', message_text)
    if not match: return
    try:
        operator = match.group(1); value = int(match.group(2))
    except (ValueError, IndexError): return

    if operator == '+':
        if value == 300: await update.message.reply_animation(GIF_300); return
        if value > 1000: await update.message.reply_animation(GIF_OVER_1000); return
        if value > 10: await update.message.reply_photo(PNG_OVER_10); return
        
        current_score = load_scores(chat_id); new_score = current_score + value
        save_scores(chat_id, new_score)
        await update.message.reply_animation(animation=GIF_PLUS, caption=f"🏆 <b>Рахунок потужності:</b> <code>{new_score}</code>", parse_mode=ParseMode.HTML)
        return

    if operator == '-':
        if value > 1000: await update.message.reply_animation(GIF_OVER_1000); return
        if value > 10: await update.message.reply_photo(PNG_OVER_10); return
        
        current_score = load_scores(chat_id); new_score = current_score - value
        save_scores(chat_id, new_score)
        await update.message.reply_animation(animation=GIF_MINUS, caption=f"🏆 <b>Рахунок потужності:</b> <code>{new_score}</code>", parse_mode=ParseMode.HTML)
        return

# --- ⭐️⭐️⭐️ НОВАЯ ЛОГИКА ЗАПУСКА (WEBHOOK) ⭐️⭐️⭐️ ---

# 1. Настраиваем Планировщик и Приложение
job_queue = JobQueue()
application = (
    Application.builder()
    .token(TOKEN)
    .job_queue(job_queue)
    .build()
)

# 2. Добавляем наши задачи в планировщик и обработчик
UKRAINE_TZ = pytz.timezone('Europe/Kyiv')
job_time = datetime.time(hour=20, minute=0, tzinfo=UKRAINE_TZ)
job_queue.run_daily(send_evening_message, time=job_time, days=(0, 1, 2, 3, 4, 5, 6))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# 3. Настраиваем Веб-сервер (Flask)
app = Flask('')

@app.route("/")
def home():
    """Этот роут нужен для UptimeRobot, чтобы сервис не "засыпал"."""
    return "Бот 'ПОТУЖНИЙ' активний! (Режим Webhook)"

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    """Этот роут "слушает" Telegram."""
    update_data = await request.json
    update = Update.de_json(update_data, application.bot)
    await application.process_update(update)
    return "ok", 200

# 4. Главная функция запуска
async def main_startup():
    """Запускает все (веб-хук, планировщик и веб-сервер)."""
    if not RENDER_URL:
        logger.error("RENDER_EXTERNAL_URL не найден! Не могу установить веб-хук.")
        return

    # Устанавливаем веб-хук, чтобы Telegram знал, куда слать апдейты
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Веб-хук успешно установлен на: {webhook_url}")
    
    # Запускаем JobQueue (планировщик) в фоновом режиме
    await job_queue.start()
    logger.info("Планировщик (JobQueue) запущен.")
    
    # Запускаем Flask-сервер (UptimeRobot + Webhook)
    # (Мы используем встроенный сервер Flask, т.к. Render.com хорошо с ним справляется)
    port = int(os.environ.get('PORT', 8080))
    print(f"Запуск веб-сервера Flask на порту {port}...")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    if not TOKEN or not UPSTASH_URL or not UPSTASH_TOKEN:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют TOKEN, UPSTASH_URL или UPSTASH_TOKEN!")
    else:
        # Запускаем всю нашу асинхронную логику
        asyncio.run(main_startup())

