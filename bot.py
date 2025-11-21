diff --git a/bot.py b/bot.py
index 5ba1eca609e9c12be1a9a9b43b6318f482dc0fbd..6782f96deb87fbd31fb84420658bb328bd3ecd87 100644
--- a/bot.py
+++ b/bot.py
@@ -108,165 +108,227 @@ def estimate_station(object_type, region, payment):
     if payment < 2500:
         stype = "Сетевая"
         size = "3–5 кВт"
         price = "170–260 тыс. руб."
     elif payment < 6000:
         stype = "Гибридная"
         size = "5–10 кВт"
         price = "280–480 тыс. руб."
     else:
         stype = "Гибридная / Автономная"
         size = "10–15 кВт"
         price = "620–950 тыс. руб."
 
     return (
         f"📊 *Предварительный расчёт станции*\n\n"
         f"🏠 Объект: {object_type}\n"
         f"📍 Регион: {region}\n"
         f"⚡ Платёж: {payment} руб/мес\n\n"
         f"Тип: *{stype}*\n"
         f"Мощность: *{size}*\n"
         f"Стоимость: *{price}*\n\n"
         f"Могу передать инженеру для точного расчёта. "
         f"Хочешь? Напиши имя и номер телефона."
     )
 
+
+def calculate_solar_options(lead: dict) -> str:
+    """
+    Примерный расчёт станции по данным клиента.
+    Это НЕ точная смета, а понятная прикидка для диалога.
+    """
+    raw_bill = lead.get("bill", "")
+    digits = re.sub(r"[^\d]", "", raw_bill)
+    try:
+        bill = int(digits)
+    except ValueError:
+        bill = 5000  # если человек написал «около пяти», ставим дефолт
+
+    # Примем средний тариф ~6 ₽/кВт⋅ч
+    tariff = 6.0
+    monthly_kwh = bill / tariff
+    yearly_kwh = monthly_kwh * 12
+
+    # Очень грубо: 1 кВт СЭС даёт ~110–130 кВт⋅ч/мес
+    power_kw = round(monthly_kwh / 120, 1)
+    if power_kw < 1:
+        power_kw = 1.0
+
+    # Примерный бюджет (диапазон) — 70–110 тыс ₽ за 1 кВт
+    cost_min = int(power_kw * 70000)
+    cost_max = int(power_kw * 110000)
+
+    # Ориентировочная окупаемость
+    avg_cost = (cost_min + cost_max) / 2
+    payback_years = round(avg_cost / (bill * 12), 1)
+
+    obj = (lead.get("object", "") + " " + lead.get("region", "")).lower()
+
+    if any(w in obj for w in ["производ", "завод", "магазин", "склад", "бизнес"]):
+        station_type = "гибридная или сетевая коммерческая станция"
+    elif any(w in obj for w in ["дача", "дерев", "село", "ферма"]):
+        station_type = "автономная или гибридная станция (с аккумуляторами)"
+    else:
+        station_type = "домашняя сетевая или гибридная СЭС"
+
+    text = (
+        "🔎 Черновая прикидка по вашим данным:\n"
+        f"• Тип объекта: {lead.get('object', '—')}\n"
+        f"• Регион: {lead.get('region', '—')}\n"
+        f"• Счёт за электричество: ~{bill} ₽/мес\n\n"
+        f"⚡ Ориентировочная мощность станции: ~{power_kw} кВт\n"
+        f"🏗 Предполагаемый тип станции: {station_type}\n"
+        f"💰 Примерный бюджет под ключ: от {cost_min} до {cost_max} ₽\n"
+        f"⏱ Окупаемость: примерно {payback_years} лет (очень грубая оценка).\n"
+    )
+    return text
+
+
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
+        context.user_data["lead"] = lead
 
         await update.message.reply_text(
             f"Спасибо, {lead.get('name', '')}! 🙌\n"
             f"Инженер перезвонит на номер {phone} в ближайшее время.\n"
-            f"Если хочешь — могу рассказать про окупаемость или варианты СЭС."
+            f"Если хочешь — могу ещё подсказать по окупаемости или доработке проекта."
         )
         return
 
     # ----------------------------------------
     # ЭТАП 4 — ИМЯ
     # ----------------------------------------
     if stage == "waiting_for_name":
         lead["name"] = text
+        context.user_data["lead"] = lead
         context.user_data["stage"] = "waiting_for_phone"
         await update.message.reply_text("Теперь номер телефона? 📱")
         return
 
     # ----------------------------------------
-    # ЭТАП 3 — ПЛАТЁЖ
+    # ЭТАП 3 — ПЛАТЁЖ + РАСЧЁТ СТАНЦИИ
     # ----------------------------------------
- 
-if stage == "waiting_for_bill":
-    lead["bill"] = text
-    context.user_data["lead"] = lead
-
-    # расчёт станции
-    object_type = lead.get("object")
-    region = lead.get("region")
-    payment = text
+    if stage == "waiting_for_bill":
+        lead["bill"] = text
+        context.user_data["lead"] = lead
+        context.user_data["stage"] = "waiting_for_name"
 
-    estimate = estimate_station(object_type, region, payment)
+        # 1) наш инженерный черновой калькулятор
+        calc_text = calculate_solar_options(lead)
 
-    await update.message.reply_text(estimate)
+        # 2) комментарий от нейросети, как от «инженера-консультанта»
+        ai_comment = await ask_groq(
+            "Вот данные клиента и предварительный инженерный расчёт. "
+            "Аккуратно подтверди или скорректируй оценку, добавь 2–3 практичных совета. "
+            "Не проси повторно имя/телефон и не собирай данные ещё раз.\n\n"
+            f"Данные клиента: {json.dumps(lead, ensure_ascii=False)}\n\n"
+            f"Черновая оценка: {calc_text}"
+        )
 
-    context.user_data["stage"] = "waiting_for_name"
-    await update.message.reply_text("Как тебя зовут? 😊")
-    return
+        await update.message.reply_text(calc_text)
+        await update.message.reply_text(ai_comment)
+        await update.message.reply_text("Если всё в целом подходит — как тебя зовут? 🙂")
+        return
 
     # ----------------------------------------
     # ЭТАП 2 — РЕГИОН
     # ----------------------------------------
     if stage == "waiting_for_region":
         lead["region"] = text
+        context.user_data["lead"] = lead
         context.user_data["stage"] = "waiting_for_bill"
         await update.message.reply_text("А сколько платите за электричество в месяц? 💡")
         return
 
     # ----------------------------------------
     # ЭТАП 1 — ТИП ОБЪЕКТА
     # ----------------------------------------
     if stage == "waiting_for_object":
         lead["object"] = text
+        context.user_data["lead"] = lead
         context.user_data["stage"] = "waiting_for_region"
         await update.message.reply_text("В каком регионе объект? 🗺️")
         return
 
     # ----------------------------------------
-    # ЭТАП DONE — свободное общение
+    # ЭТАП DONE — лид собран, дальше свободный ИИ-диалог
     # ----------------------------------------
     if stage == "done":
         reply = await ask_groq(text)
         await update.message.reply_text(reply)
         return
 
     # ----------------------------------------
-    # СВОБОДНЫЙ ЧАТ (начало)
+    # СВОБОДНЫЙ ЧАТ (начало) — stage == "chat"
     # ----------------------------------------
- if stage == "chat":
-    # если человек сам пишет набор данных — делаем автоанализ
-    payment = extract_numbers(text)
-    if payment and any(w in text.lower() for w in ["дом", "квартира", "дача"]):
-        lead["object"] = "дом"
-        lead["region"] = "регион не указан"
-        lead["bill"] = payment
-
-        estimate = estimate_station(lead["object"], lead["region"], payment)
-
-        await update.message.reply_text(estimate)
-        await update.message.reply_text("Хочешь точный расчёт? Напиши имя и номер телефона.")
-        context.user_data["stage"] = "waiting_for_name"
-        context.user_data["lead"] = lead
-        return
+    if stage == "chat":
+        # Если человек говорит про дом, свет, счета → запуск сбора данных
+        triggers = [
+            "дом", "квартира", "дача", "коттедж",
+            "электричество", "свет", "квт", "кВт",
+            "счёт", "оплата", "энергия", "сэс", "солнечн"
+        ]
+
+        if any(word in text.lower() for word in triggers):
+            context.user_data["stage"] = "waiting_for_object"
+            context.user_data["lead"] = {}
+            await update.message.reply_text(
+                "Могу прикинуть солнечную станцию 🔆\n"
+                "Для начала — что за объект (дом, дача, бизнес)?"
+            )
+            return
 
-    # обычное общение через GROQ
-    reply = await ask_groq(text)
-    await update.message.reply_text(reply)
-    return
+        # Иначе — обычный ИИ-ответ (болтовня, советы и т.д.)
+        reply = await ask_groq(text)
+        await update.message.reply_text(reply)
+        return
 
 
 
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
 

 
