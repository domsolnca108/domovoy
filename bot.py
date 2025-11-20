  import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ключи API из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Состояния для ConversationHandler
(
    TYPE_OBJECT,
    REGION,
    ELECTRICITY_BILL,
    POWER_OUTAGES,
    FINAL_SUMMARY,
) = range(5)

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

# Функция для запроса к DeepSeek API
async def get_deepseek_response(user_message: str, conversation_history: list) -> str:
    """Отправляет запрос к DeepSeek API и возвращает ответ."""
    
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
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek: {e}")
        return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже."

# Команда /start - начало диалога
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и спрашивает тип объекта."""
    
    # Инициализируем историю диалога для контекста пользователя
    context.user_data['conversation_history'] = []
    
    # Приветственное сообщение в стиле Домового
    welcome_text = """🏡 Домовой Дом Солнца на связи.

Что за объект у вас: дом, квартира, бизнес? И сколько в среднем платите за свет в месяц?"""
    
    await update.message.reply_text(welcome_text)
    
    return TYPE_OBJECT

# Обработчик ответов пользователя
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает сообщения пользователя и взаимодействует с DeepSeek."""
    
    user_message = update.message.text
    user_id = update.message.from_user.id
    
    # Получаем или инициализируем историю диалога для этого пользователя
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = []
    
    # Добавляем сообщение пользователя в историю
    context.user_data['conversation_history'].append({"role": "user", "content": user_message})
    
    # Получаем ответ от DeepSeek
    bot_response = await get_deepseek_response(
        user_message, 
        context.user_data['conversation_history']
    )
    
    # Добавляем ответ бота в историю
    context.user_data['conversation_history'].append({"role": "assistant", "content": bot_response})
    
    # Отправляем ответ пользователю
    await update.message.reply_text(bot_response)
    
    # Если в ответе бота есть предложение оставить контакты, переходим в финальное состояние
    if any(keyword in bot_response.lower() for keyword in ['контакт', 'телефон', 'номер', 'инженер']):
        return FINAL_SUMMARY
    
    return TYPE_OBJECT

# Обработчик для сбора контактов
async def get_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает контактные данные."""
    
    contact_text = """Отлично! Для точного расчета инженеру нужны ваши контакты.

Напишите, пожалуйста, ваше имя и номер телефона в формате:
Иван +7 900 123-45-67"""
    
    await update.message.reply_text(contact_text)
    
    return FINAL_SUMMARY

# Обработчик финального шага - сохранение контактов
async def save_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет контактные данные и завершает диалог."""
    
    user_contacts = update.message.text
    
    # Здесь должна быть логика сохранения контактов (в БД, файл, или отправка куда-то)
    # Для примера просто логируем
    logger.info(f"Получены контакты от пользователя {update.message.from_user.id}: {user_contacts}")
    
    # Сохраняем контакты в user_data для возможного дальнейшего использования
    context.user_data['user_contacts'] = user_contacts
    
    thank_you_text = """✅ Спасибо! Ваши контакты сохранены.

Инженер свяжется с вами в ближайшее время для бесплатного замера и точного расчета.

До связи! 🏡"""
    
    await update.message.reply_text(thank_you_text)
    
    # Очищаем данные диалога
    context.user_data.clear()
    
    return ConversationHandler.END

# Команда /cancel для отмены диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог прерван. Если потребуется консультация - напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Основная функция
def main() -> None:
    """Запускает бота."""
    
    # Создаем Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Настраиваем ConversationHandler для управления диалогом
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TYPE_OBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message)
            ],
            FINAL_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_contacts)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
