import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# --- Настройка логирования ---
# Устанавливаем базовый уровень INFO
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Приглушаем "шумные" библиотеки, которые "спамят" в лог
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("telegram.bot").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Функции-обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user_name}! Отправь мне '+' или '-'.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (+ / -)"""
    text = update.message.text
    
    if text == "+":
        await update.message.reply_text("Вы прислали ПЛЮС 👍")
    elif text == "-":
        await update.message.reply_text("Вы прислали МИНУС 👎")
    else:
        # Ответ на любой другой текст
        await update.message.reply_text(f"Я не знаю, что делать с '{text}'. Попробуй '+' или '-'.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные Update."""
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
    # Обратите внимание: мы НЕ импортируем 'Bot' отдельно,
    # Application.builder() делает это за нас. 
    # Это и есть исправление вашей ошибки.
    application = Application.builder().token(TOKEN).build()

    # 3. Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # 4. Запускаем бота
    logger.info("Бот запускается...")
    # Этот метод (run_polling) использует 'getUpdates', который мы видели в ваших логах
    # Он будет работать, т.к. мы УДАЛИЛИ Webhook
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

