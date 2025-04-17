import logging
import openai
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
import random
import os
import json

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# === ЛОГИ ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === ХРАНИЛИЩЕ ===
user_data = {}
daily_habits = {}
daily_journal = {}
user_goals = {}
user_ids = set()

# === КОДЕКС ВОИНА ===
WARRIOR_CODE = (
    "1. Я иду вперёд, несмотря на страх.\n"
    "2. Я честен с собой и другими.\n"
    "3. Я укрепляю тело, дух и ум.\n"
    "4. Я действую, даже когда не хочется.\n"
    "5. Я выбираю путь, а не комфорт."
)

HELP_TEXT = (
    "📖 *Доступные команды:*\n"
    "/start — начать диалог с ботом\n"
    "/дневник [текст] — записать мысль или состояние в дневник\n"
    "/привычка [название] — отметить выполненную привычку\n"
    "/цель [описание] — добавить цель\n"
    "/цели — показать список целей и прогресс\n"
    "/шаг — отметить шаг по первой цели\n"
    "/отчёт — показать прогресс за сегодня\n"
    "/путь — показать Кодекс Воина\n"
    "/помощь — показать эту справку"
)

# === GPT-ФУНКЦИЯ ===
def generate_response(user_id: int, user_message: str) -> str:
    messages = user_data.get(user_id, [{
        "role": "system",
        "content": "Ты — личный помощник Андемиркана. Ты помогаешь ему идти по философии 'Путь Воина', напоминаешь о его кодексе, поддерживаешь его морально, помогаешь вести дневник, привычки и цели."
    }])
    messages.append({"role": "user", "content": user_message})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=500,
        temperature=0.7
    )
    reply = response["choices"][0]["message"]["content"]
    messages.append({"role": "assistant", "content": reply})
    user_data[user_id] = messages[-10:]
    return reply

# === СОХРАНЕНИЕ В ФАЙЛ ===
def save_to_file():
    with open("habits.json", "w", encoding="utf-8") as f:
        json.dump(daily_habits, f, ensure_ascii=False, indent=2)
    with open("journal.json", "w", encoding="utf-8") as f:
        json.dump(daily_journal, f, ensure_ascii=False, indent=2)
    with open("goals.json", "w", encoding="utf-8") as f:
        json.dump(user_goals, f, ensure_ascii=False, indent=2)

def load_from_file():
    global daily_habits, daily_journal, user_goals
    if os.path.exists("habits.json"):
        with open("habits.json", "r", encoding="utf-8") as f:
            daily_habits = json.load(f)
    if os.path.exists("journal.json"):
        with open("journal.json", "r", encoding="utf-8") as f:
            daily_journal = json.load(f)
    if os.path.exists("goals.json"):
        with open("goals.json", "r", encoding="utf-8") as f:
            user_goals = json.load(f)

# === КОМАНДЫ ===
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_ids.add(user_id)
    update.message.reply_text("Привет, Андемиркан. Я здесь, чтобы поддерживать твой Путь Воина. Готов идти вместе.")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_ids.add(user_id)
    user_message = update.message.text

    if user_message.startswith("/дневник"):
        text = user_message.replace("/дневник", "").strip()
        if text:
            today = datetime.now().strftime("%Y-%m-%d")
            daily_journal.setdefault(str(user_id), {}).setdefault(today, []).append(text)
            update.message.reply_text("Записал в дневник. Продолжай идти.")
            save_to_file()
        else:
            update.message.reply_text("Напиши что-то после команды /дневник.")
    elif user_message.startswith("/привычка"):
        text = user_message.replace("/привычка", "").strip()
        if text:
            today = datetime.now().strftime("%Y-%m-%d")
            daily_habits.setdefault(str(user_id), {}).setdefault(today, []).append(text)
            update.message.reply_text(f"Отмечено: {text}. Ты держишь ритм.")
            save_to_file()
        else:
            update.message.reply_text("Напиши название привычки после /привычка.")
    elif user_message.startswith("/цель"):
        text = user_message.replace("/цель", "").strip()
        if text:
            user_goals.setdefault(str(user_id), []).append({"goal": text, "progress": 0})
            update.message.reply_text("Цель добавлена. Начни движение к ней.")
            save_to_file()
        else:
            update.message.reply_text("Напиши формулировку цели после /цель.")
    elif user_message.startswith("/шаг"):
        uid = str(user_id)
        if uid in user_goals and user_goals[uid]:
            user_goals[uid][0]["progress"] += 1
            update.message.reply_text(f"Отмечен шаг к цели: {user_goals[uid][0]['goal']}")
            save_to_file()
        else:
            update.message.reply_text("У тебя пока нет цели. Добавь с помощью /цель")
    elif user_message.startswith("/цели"):
        uid = str(user_id)
        if uid in user_goals and user_goals[uid]:
            text = "\n".join([f"{g['goal']} — шагов: {g['progress']}" for g in user_goals[uid]])
            update.message.reply_text(f"🎯 Твои цели:\n{text}")
        else:
            update.message.reply_text("Целей пока нет. Добавь с помощью /цель")
    elif user_message.startswith("/отчёт"):
        today = datetime.now().strftime("%Y-%m-%d")
        journal_entries = daily_journal.get(str(user_id), {}).get(today, [])
        habits_done = daily_habits.get(str(user_id), {}).get(today, [])

        report = f"\n📘 *ДНЕВНИК*: {'\n'.join(journal_entries) if journal_entries else 'пусто'}"
        report += f"\n\n✅ *ПРИВЫЧКИ*: {'\n'.join(habits_done) if habits_done else 'не отмечены'}"
        update.message.reply_text(report, parse_mode=telegram.ParseMode.MARKDOWN)
    elif user_message.startswith("/путь"):
        update.message.reply_text(f"🛡 *Твой Кодекс Воина:*\n\n{WARRIOR_CODE}", parse_mode=telegram.ParseMode.MARKDOWN)
    elif user_message.startswith("/помощь"):
        update.message.reply_text(HELP_TEXT, parse_mode=telegram.ParseMode.MARKDOWN)
    else:
        reply = generate_response(user_id, user_message)
        update.message.reply_text(reply)

# === ПЛАНИРОВЩИК ===
def send_reminders(context: CallbackContext):
    for user_id in user_ids:
        context.bot.send_message(chat_id=user_id, text="Хочешь записать мысли в дневник, отметить привычку или сделать шаг к цели?")

# === ПРОГРЕСС ===
def send_progress_report(context: CallbackContext):
    for user_id in user_ids:
        uid = str(user_id)
        journal_count = sum(len(entries) for entries in daily_journal.get(uid, {}).values())
        habit_days = len(daily_habits.get(uid, {}))
        goals = user_goals.get(uid, [])
        goal_text = "\n".join([f"{g['goal']} — шагов: {g['progress']}" for g in goals]) if goals else "нет"

        messages = [
            "Ты идёшь. Не быстро, но твёрдо. Продолжай.",
            "Вижу, ты не сдаёшься. Это и есть путь.",
            "Путь Воина не в том, чтобы быть идеальным — а в том, чтобы вставать."
        ]

        message = f"📊 *Твой прогресс*:\nЗаписей в дневнике: {journal_count}\nДней с привычками: {habit_days}\nЦели:\n{goal_text}\n\n{random.choice(messages)}"
        context.bot.send_message(chat_id=user_id, text=message, parse_mode=telegram.ParseMode.MARKDOWN)

# === ЗАПУСК ===
def main():
    load_from_file()

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    moscow_tz = timezone("Europe/Moscow")
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminders, 'cron', hour=9, minute=0, args=[updater.bot], timezone=moscow_tz)
    scheduler.add_job(send_reminders, 'cron', hour=20, minute=0, args=[updater.bot], timezone=moscow_tz)
    scheduler.add_job(send_progress_report, 'cron', day='1,15', hour=12, minute=0, args=[updater.bot], timezone=moscow_tz)
    scheduler.start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
