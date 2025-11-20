import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------
# ЛОГИ
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# ENV
# -------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -------------------------------------------------
# СИСТЕМНЫЙ ПРОМПТ ДЛЯ ДОМОГО
# -------------------------------------------------
SYSTEM_PROMPT = """
Ты — «Домовой Дом Солнца». 
Стиль общения: коротко, строго, без воды. Профессиональный энергетик.
Всегда ориентируешься на выгоду, окупаемость, подбор типа солнечной станции.
Задача — быстро понять:
- объект (дом, бизнес, площадь)
- регион
- платёж за свет
- есть ли отключения
- цель: экономия / резерв / автономия

Ты даёшь:
- рекомендуемый тип станции (сетевая / гибридная / автономная / резервная)
- примерную мощность
- ориентировочную стоимость
- срок окупаемости
- пользу

Финальная цель: вывести человека на заявку: попросить имя и телефон.
"""

# -------------------------------------------------
# ФУНКЦИЯ ЗАПРОСА В GROQ
# -------------------------------------------------
async def ask_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mixtral-8x7b-32768",   # стабильная и быстрая модель Groq
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()

            if resp.status != 200:
                return f"⚠ Ошибка Groq API: {data}"

            try:
                return data["choices"][0]["message"]["content"]
            except Exception:
                return f"⚠ Ошибка в ответе модели: {data}"

# -------------------------------------------------
# ХЕНДЛЕРЫ
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏡 Домовой Дом Солнца здесь. Готов подсказать, сколько ты переплачиваешь за свет.\n\n"
        "Напиши:\n1) Что за объект (дом, бизнес)\n2) Регион\n3) Средний платёж за электроэнергию"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши параметры дома: тип, регион и сколько платишь за свет. Я подскажу, что выгодно."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    logger.info(f"Message from {update.effective_user.id}: {user_text}")

    reply = await ask_groq(user_text)
    await update.message.reply_text(reply)

# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    if TELEGRAM_BOT_TOKEN is None:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)

# -------------------------------------------------
if __name__ == "__main__":
    main()
