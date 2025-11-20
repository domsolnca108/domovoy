import os
import logging
import requests

from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

# ---------- ЛОГИ ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛЮЧИ ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Не задан DEEPSEEK_API_KEY")

# ---------- СИСТЕМНЫЙ ПРОМПТ ----------
SYSTEM_PROMPT = """
Ты — «Домовой Дом Солнца», строгий, мудрый и короткий в ответах.
Помогаешь человеку рассчитать СЭС, понять мощность и выгоду.
Отвечай коротко и по делу, мягко подводи к заявке и оставлению телефона.
"""

# ---------- ФУНКЦИЯ ОБРАЩЕНИЯ К DEEPSEEK ----------
def ask_deepseek(prompt: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(url, json=data, headers=headers, timeout=30)
    except Exception as e:
        logger.error(f"DeepSeek request error: {e}")
        return "Что-то пошло не так с сервером. Попробуйте ещё раз или позвоните: +7 906 535-27-40."

    if resp.status_code == 200:
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek parse error: {e}")
            return "Ответ сервера непонятен. Давайте попробуем ещё раз одним сообщением, без лишних деталей."

    logger.error(f"DeepSeek API error: {resp.status_code} {resp.text}")
    return "Ошибка связи с нейросетью. Попробуйте ещё раз или позвоните: +7 906 535-27-40."

# ---------- ОБРАБОТЧИК /start ----------
def start(update: Update, context: CallbackContext) -> None:
    text = (
        "🏡 Домовой Дом Солнца на связи.\n\n"
        "Коротко и по делу помогу прикинуть солнечную станцию.\n\n"
        "Напишите:\n"
        "• Что за объект (дом / бизнес)\n"
        "• Регион\n"
        "• Сколько платите за свет в месяц\n"
    )
    update.message.reply_text(text)

# ---------- ОБРАБОТЧИК ЛЮБОГО ТЕКСТА ----------
def handle_message(update: Update, context: CallbackContext) -> None:
    user_text = update.message.text or ""
    logger.info(f"User {update.effective_user.id} wrote: {user_text!r}")

    reply = ask_deepseek(user_text)
    update.message.reply_text(reply)

# ---------- ТОЧКА ВХОДА ----------
def main() -> None:
    # создаём Updater со старым, но стабильным API
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    logger.info("✅ Домовой Дом Солнца запущен. Ждём сообщений.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
