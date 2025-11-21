import os
import json
import re
import logging
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

LEADS_FILE = "leads.json"

# ===========================
# SYSTEM PROMPT
# ===========================
SYSTEM_PROMPT = """
Ты — Домовой Дом Солнца ☀️
Мягкий, умный, дружелюбный ассистент.
Общаешься свободно и живо, как ИИ-помощник, но мягко подводишь к продажам солнечной электростанции.

ТВОЯ ЛОГИКА (ОЧЕНЬ ВАЖНО):
1. Поддерживай свободный диалог. Можно болтать, шутить, отвечать на любые темы.
2. Если видишь, что пользователь говорит про дом/электроэнергию/счета — начинай СБОР ДАННЫХ:
   - тип объекта
   - регион
   - платеж в месяц
3. После получения трёх параметров — СДЕЛАЙ АНАЛИЗ (кратко, по делу).
4. После анализа — спроси:
   "Хочешь расчёт инженера? Напиши имя и номер телефона."
5. Когда человек прислал телефон — НЕ ЗАДАВАЙ НОВЫХ ВОПРОСОВ.
   Просто:
   - поблагодари
   - скажи, что инженер свяжется
   - дай бонус (совет, пример окупаемости)
6. После финала — пользователь может продолжать общаться на любую тему (ты снова свободный ассистент).
7. НИКОГДА не начинай сбор данных повторно после получения номера.
"""


# ===========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===========================

def extract_phone(text):
    pattern = r'(\+7|8)\s?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    match = re.search(pattern, text)
    return match.group(0) if match else None


async def ask_groq(prompt: str) -> str:
    """Отправка запроса к GROQ"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                return f"Ошибка Groq API: {await resp.text()}"
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


def save_lead(user_id, lead_data):
    """Сохраняем лид в leads.json"""
    if not os.path.exists(LEADS_FILE):
        with open(LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        all_leads = json.load(f)

    all_leads[user_id] = lead_data

    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_leads, f, ensure_ascii=False, indent=2)

    logger.info(f"Лид сохранён: {lead_data}")


# ===========================
# ОБРАБОТЧИКИ КОМАНД
# ===========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stage"] = "chat"
    context.user_data["lead"] = {}

    await update.message.reply_text(
        "Привет! Я Домовой Дом Солнца ☀️\n"
        "Можем просто пообщаться или могу помочь рассчитать солнечную станцию.\n"
        "О чём хочешь поговорить?"
    )


# ===========================
# ГЛАВНЫЙ ОБРАБОТЧИК
# ===========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stage = context.user_data.get("stage", "chat")
    lead = context.user_data.get("lead", {})

    # ----------------------------------------
    # ЭТАП 5 — ЧЕЛОВЕК ДАЛ ТЕЛЕФОН
    # ----------------------------------------
    phone = extract_phone(text)
    if stage == "waiting_for_phone":
        if not phone:
            await update.message.reply_text("Напиши номер в формате +7… 🌞")
            return

        lead["phone"] = phone
        lead["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_lead(str(update.message.from_user.id), lead)

        context.user_data["stage"] = "done"

        await update.message.reply_text(
            f"Спасибо, {lead.get('name', '')}! 🙌\n"
            f"Инженер перезвонит на номер {phone} в ближайшее время.\n"
            f"Если хочешь — могу рассказать про окупаемость или варианты СЭС."
        )
        return

    # ----------------------------------------
    # ЭТАП 4 — ИМЯ
    # ----------------------------------------
    if stage == "waiting_for_name":
        lead["name"] = text
        context.user_data["stage"] = "waiting_for_phone"
        await update.message.reply_text("Теперь номер телефона? 📱")
        return

    # ----------------------------------------
    # ЭТАП 3 — ПЛАТЁЖ
    # ----------------------------------------
    if stage == "waiting_for_bill":
        lead["bill"] = text
        context.user_data["stage"] = "waiting_for_name"

        summary = f"{lead}"
        groq_answer = await ask_groq(f"Параметры клиента: {summary}. Дай анализ.")

        await update.message.reply_text(
            groq_answer + "\n\nКак тебя зовут? 😊"
        )
        return

    # ----------------------------------------
    # ЭТАП 2 — РЕГИОН
    # ----------------------------------------
    if stage == "waiting_for_region":
        lead["region"] = text
        context.user_data["stage"] = "waiting_for_bill"
        await update.message.reply_text("А сколько платите за электричество в месяц? 💡")
        return

    # ----------------------------------------
    # ЭТАП 1 — ТИП ОБЪЕКТА
    # ----------------------------------------
    if stage == "waiting_for_object":
        lead["object"] = text
        context.user_data["stage"] = "waiting_for_region"
        await update.message.reply_text("В каком регионе объект? 🗺️")
        return

    # ----------------------------------------
    # ЭТАП DONE — свободное общение
    # ----------------------------------------
    if stage == "done":
        reply = await ask_groq(text)
        await update.message.reply_text(reply)
        return

    # ----------------------------------------
    # СВОБОДНЫЙ ЧАТ (начало)
    # ----------------------------------------
    if stage == "chat":
        # Если человек говорит про дом, свет, счета → запуск сбора данных
        triggers = ["дом", "квартира", "дача", "свет", "электричество", "квт", "оплата", "сэс"]

        if any(word in text.lower() for word in triggers):
            context.user_data["stage"] = "waiting_for_object"
            await update.message.reply_text(
                "Хочешь — рассчитаю станцию 🔆\n"
                "Для этого напиши, что за объект (дом, дача, бизнес)?"
            )
            return

        # Иначе — обычный ИИ-ответ
        reply = await ask_groq(text)
        await update.message.reply_text(reply)
        return


# ===========================
# ЗАПУСК
# ===========================

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()

