import logging
import os
import datetime
from zoneinfo import ZoneInfo  # Для указания часового пояса

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# --- Настройка логирования (чтобы убрать "спам") ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Константы ---
KYIV_TIMEZONE = ZoneInfo("Europe/Kyiv")
DAILY_GREETING_TIME = datetime.time(hour=20, minute=0, tzinfo=KYIV_TIMEZONE)

# --- Функции-обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    Приветствует пользователя и запускает ежедневное задание.
    """
    user_name = update.effective_user.first_name
    chat_id = update.effective_chat.id
    
    # Инициализируем счет, если его еще нет
    context.chat_data.setdefault('power_score', 0)

    # --- Настройка ежедневного задания ---
    job_name = f'daily_greeting_{chat_id}'

    # 1. Сначала удаляем старое задание (если оно было), чтобы избежать дубликатов
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if current_jobs:
        for job in current_jobs:
            job.schedule_removal()
        logger.info(f"Удалено старое ежедневное задание для чата {chat_id}")

    # 2. Создаем новое задание
    context.job_queue.run_daily(
        send_daily_greeting,
        time=DAILY_GREETING_TIME,
        chat_id=chat_id,
        name=job_name
    )
    
    logger.info(f"Установлено ежедневное задание для чата {chat_id} на {DAILY_GREETING_TIME}")
    
    await update.message.reply_text(
        f"Привіт, {user_name}! Я бот 'ПОТУЖНИЙ'.\n"
        f"Я буду рахувати 'потужність' в цьому чаті.\n"
        f"Просто пишіть '+' або '-' у повідомленнях.\n\n"
        f"Щоб перевірити рахунок, введіть /score.\n"
        f"Я також буду вітати вас щодня о 20:00."
    )

async def check_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /score.
    Показывает текущий счет потужності.
    """
    # .get() безопаснее - вернет 0, если счета еще нет
    score = context.chat_data.get('power_score', 0)
    await update.message.reply_text(f"🔥 Поточна Потужність: {score}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик всех текстовых сообщений.
    Считает + и - в тексте.
    """
    # Убедимся, что у нас есть сообщение (а не, например, изменение в чате)
    if not update.message or not update.message.text:
        return

    text = update.message.text
    
    # Считаем *каждое* вхождение символов
    plus_count = text.count('+')
    minus_count = text.count('-')

    # Если в сообщении нет ни плюсов, ни минусов - ничего не делаем
    if plus_count == 0 and minus_count == 0:
        return

    # Получаем текущий счет (или 0, если его нет)
    current_score = context.chat_data.get('power_score', 0)
    
    # Считаем новый счет
    new_score = current_score + plus_count - minus_count
    
    # Сохраняем новый счет
    context.chat_data['power_score'] = new_score
    
    logger.info(f"Чат {update.effective_chat.id}: {plus_count} плюсов, {minus_count} минусов. "
                f"Счет изменен с {current_score} на {new_score}.")

    # Отвечаем в чат (можно закомментировать, если не хотите спамить)
    await update.message.reply_text(f"Зараховано! Потужність: {new_score}")

async def send_daily_greeting(context: ContextTypes.DEFAULT_TYPE):
    """
    Функция, которую вызывает JobQueue.
    Отправляет ежедневное приветствие.
    """
    job = context.job
    chat_id = job.chat_id
    
    logger.info(f"Отправка ежедневного приветствия в чат {chat_id}")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Добрий вечір! 👋\nШо у вас по Потужності?"
        )
        
        # Опционально: можно также отправить текущий счет
        # score = context.chat_data.get('power_score', 0)
        # await context.bot.send_message(chat_id=chat_id, text=f"Поточний рахунок: {score}")

    except Exception as e:
        logger.error(f"Не удалось отправить сообщение в чат {chat_id}: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- Основная функция ---

def main():
    """Главная функция для запуска бота"""
    
    # 1. Получаем токен из переменных окружения (как требует Render)
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.critical("Ошибка: Необходима переменная окружения TELEGRAM_TOKEN!")
        return

    # 2. Создаем объект Application
    application = Application.builder().token(TOKEN).build()

    # 3. Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("score
