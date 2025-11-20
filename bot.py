import os
import logging
import re
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT = """
Ты — Домовой Дом Солнца, строгий, мудрый и краткий.
Ты эксперт по солнечным электростанциям.

ВЕДЕНИЕ ДИАЛОГА:

1. Если ты получаешь параметры (дом, регион, платеж), дай краткий анализ.
2. После анализа всегда задавай один вопрос:
   "Могу передать инженеру для расчёта. Напишите имя и номер телефона."

3. Если человек прислал телефон — не задавай новые вопросы.
   Просто: поблагодари, скажи что инженер позвонит, и завершай.

4. НЕ повторай вопросы заново.
"""

# -------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------------

def extract_phone(text):
    phone_pattern = r'(\+7|8)\s?\(?\d{3}\)?\s?\d{3}-?\d{2}-?\d{2}'
    match = re.search(phone_pattern, text)
    return match.group(0) if match else None

def extract_name(text):
    name_pattern = r"(меня зовут|имя|звать)\s+([А-Яа-я]{2,20})"
    match = re.search(name_pattern, text, re.IGNORECASE)
    return match.group(2) if match else None

async def ask_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]

    return f"Ошибка Groq API: {response.text}"

# -------------------------------
# ОБРАБОТЧИКИ
# -------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stage"] = "collecting_data"

    await update.message.reply_text(
        "🏡 Домовой Дом Солнца здесь.\n"
        "Чтобы прикинуть мощность станции — скажите:\n"
        "• Что за объект (дом/квартира/бизнес)\n"
        "• Регион\n"
        "• Сколько платите за электричество в месяц?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stage = context.user_data.get("stage", "collecting_data")

    # -----------------------------
    # 1. Если ждём телефон
    # -----------------------------
    if stage == "waiting_for_contact":
        phone = extract_phone(text)
        name = extract_name(text)

        if not phone:
            await update.message.reply_text("Укажите, пожалуйста, номер телефона в формате +7…")
            return

        # Сохраняем лид
        save_lead(name, phone, context.user_data.get("object_data"))

        context.user_data["stage"] = "done"

        await update.message.reply_text(
            f"Спасибо! 👌\n"
            f"Инженер свяжется с вами по номеру {phone} в течение часа.\n"
            f"Если что — телефон компании: +7 906 535 27 40."
        )
        return

    # -----------------------------
    # 2. Основные параметры объекта
    # -----------------------------
    if stage == "collecting_data":
        context.user_data["object_data"] = text

        reply = await ask_groq(text)

        await update.message.reply_text(reply)
        await update.message.reply_text("Напишите ваше имя и номер телефона для связи:")

        context.user_data["stage"] = "waiting_for_contact"
        return

    # -----------------------------
    # 3. Стадия завершена
    # -----------------------------
    if stage == "done":
        await update.message.reply_text("Я уже передал заявку инженеру 🙌")
        return


# -------------------------------
# СОХРАНЕНИЕ ЛИДОВ
# -------------------------------

def save_lead(name, phone, details):
    """Сохраняем заявку в файл leads.txt"""

    with open("leads.txt", "a", encoding="utf-8") as f:
        f.write(f"Имя: {name}\nТелефон: {phone}\nДанные: {details}\n---\n")

    logger.info(f"Лид сохранён: {name}, {phone}")


# -------------------------------
# ЗАПУСК
# -------------------------------

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
