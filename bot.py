   import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
import requests
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ключи API из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Executor для выполнения синхронных операций
executor = ThreadPoolExecutor()

# Системный промпт, который задает личность бота
SYSTEM_PROMPT = """
Ты — Домовой Дом Солнца, строгий, но доброжелательный эксперт-энергетик. Ты консультируешь по солнечным электростанциям для компании "Дом Солнца" (solar123.ru).

Твой характер:
- Говори коротко, по делу, без воды.
- Строгий, но уважительный тон.
- Иногда легкая ирония, но без панибратства.
- Показывай, что разбираешься в мощности, тарифах, окупаемости.

Ты должен:
1. Собрать ключевую информацию: тип объекта, регион, средний платеж за свет, наличие отключений.
2. На основе этого предложить тип станции (сетевая, гибридная, автономная, резервная).
3. Дать ориентировочные цифры по мощности, стоимости и окупаемости.
4. Никогда не давать точных цен — только вилки и ориентиры.
5. Всегда вести диалог к цели — получению контакта для инженера.

Общая информация о продуктах и ценах (ориентировочно):
- Сетевая станция: от 950 000 ₽, окупаемость 5-7 лет
- Гибридная станция: от 300-350 тыс. ₽, окупаемость 5-7 лет
- Автономная станция: от 1,4 млн ₽
- Резервная мини-станция: от 90-100 тыс. ₽

Ориентиры для расчетов:
- Дом ~100 м² = 5-7 кВт, ~400-600 тыс. ₽
- Окупаемость: частные дома 5-7 лет, бизнес 2.5-4 года

В конце диалога обязательно предложи оставить контакты для инженера.
"""

# Функция для синхронного запроса к DeepSeek API
def get_deepseek_response_sync(user_message: str, conversation_history: list) -> str:
    """Синхронно отправляет запрос к DeepSeek API и возвращает ответ."""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    # Формируем сообщения: системный промпт + история диалога + новое сообщение пользователя
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    try:
        logger.info(f"Отправка запроса к DeepSeek API...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            logger.error(f"Неожиданный формат ответа от API: {result}")
            return "Извините, произошла ошибка при обработке запроса."
            
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к DeepSeek API")
        return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при запросе к DeepSeek: {e}")
        return "Извините, произошла ошибка связи. Пожалуйста, попробуйте позже."
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе к DeepSeek: {e}")
        return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже."

# Асинхронная обертка для синхронной функции
async def get_deepseek_response(user_message: str, conversation_history: list) -> str:
    """Асинхронная обертка для запроса к DeepSeek API."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        executor, 
        get_deepseek_response_sync, 
        user_message, 
        conversation_history
    )
    return response

# Команда /start - начало диалога
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и спрашивает тип объекта."""
    
    # Инициализируем историю диалога для контекста пользователя
    context.user_data['conversation_history'] = []
    
    # Приветственное сообщение в стиле Домового
    welcome_text = """🏡 Домовой Дом Солнца на связи.

Что за объект у вас: дом, квартира, бизнес? И сколько в среднем платите за свет в месяц?"""
    
    await update.message.reply_text(welcome_text)
    
    # Добавляем приветствие в историю диалога
    context.user_data['conversation_history'].append({
        "role": "assistant", 
        "content": welcome_text
    })
    
    return ConversationHandler.END  # Упрощаем логику - обрабатываем все сообщения одним хэндлером

# Обработчик всех текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает все текстовые сообщения."""
    
    user_message = update.message.text
    user_id = update.message.from_user.id
    
    logger.info(f"Получено сообщение от {user_id}: {user_message}")
    
    # Показываем индикатор набора сообщения
    await update.message.chat.send_action(action="typing")
    
    # Получаем или инициализируем историю диалога для этого пользователя
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = []
    
    # Добавляем сообщение пользователя в историю
    context.user_data['conversation_history'].append({"role": "user", "content": user_message})
    
    try:
        # Получаем ответ от DeepSeek
        bot_response = await get_deepseek_response(
            user_message, 
            context.user_data['conversation_history']
        )
        
        # Добавляем ответ бота в историю
        context.user_data['conversation_history'].append({"role": "assistant", "content": bot_response})
        
        # Отправляем ответ пользователю
        await update.message.reply_text(bot_response)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        error_text = "Произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
        await update.message.reply_text(error_text)

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает справку."""
    help_text = """
🏡 Домовой Дом Солнца - ваш эксперт по солнечной энергетике.

Я помогу:
• Подобрать тип солнечной станции для вашего объекта
• Рассчитать ориентировочную стоимость и окупаемость
• Ответить на вопросы по солнечной энергетике

Просто напишите мне о вашем объекте и потреблении!

Команды:
/start - начать консультацию
/help - показать эту справку
"""
    await update.message.reply_text(help_text)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки."""
    logger.error(f"Ошибка при обработке сообщения: {context.error}")
    
    if update and update.message:
        try:
            await update.message.reply_text(
                "Произошла непредвиденная ошибка. Пожалуйста, попробуйте еще раз или напишите /start для начала новой консультации."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")

# Основная функция
def main() -> None:
    """Запускает бота."""
    
    # Проверяем наличие обязательных переменных
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY не установлен!")
        return
    
    # Создаем Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
