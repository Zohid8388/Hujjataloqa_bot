"""
UstozGayordamBot - Telegram bot for teachers.
Features:
- /start, /help
- /register (save user info)
- /materials (list/download shared materials)
- /quiz (simple quiz with score saved)
- /attendance (mark present / view list)
- /ask (user sends a question to admins)
- Admin commands: /broadcast, /stats
Storage: SQLite
Author: ChatGPT for Zohid (template, adjust as needed)
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Tuple, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# -----------------------------
# Configuration
# -----------------------------
TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACE_WITH_YOUR_TOKEN_HERE")
# ADMIN_IDS can be comma-separated Telegram user IDs, e.g. "12345,67890"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

DB_PATH = os.getenv("DB_PATH", "ustoz_gayordam.db")
MATERIALS_FOLDER = os.getenv("MATERIALS_FOLDER", "materials")  # store files here

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------
# Database helpers
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER UNIQUE,
            name TEXT,
            registered_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER,
            date TEXT,
            note TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER,
            score INTEGER,
            total INTEGER,
            taken_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            q_text TEXT,
            options TEXT, -- pipe-separated options
            correct_index INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS asks (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER,
            question TEXT,
            asked_at TEXT,
            handled INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def db_execute(query: str, params: Tuple = (), fetch: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    data = None
    if fetch:
        data = cur.fetchall()
    conn.commit()
    conn.close()
    return data

# -----------------------------
# Seed sample quiz questions (run once)
# -----------------------------
SAMPLE_QUESTIONS = [
    ("Maktabda darslar necha soatdan boshlanadi?", "8:00|9:00|10:00|11:00", 0),
    ("Ta'lim metodikasi nima uchun muhim?", "O'quvchilarni anglash uchun|Faoliyat uchun|Baholar uchun|Hamma uchun", 0),
    ("5E modeli qaysi bosqichni o'z ichiga olmaydi?", "Engage|Explore|Explain|Evaluate", 3),  # just example
]


def seed_questions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM questions")
    if cur.fetchone()[0] == 0:
        for q_text, options, correct in SAMPLE_QUESTIONS:
            cur.execute(
                "INSERT INTO questions (q_text, options, correct_index) VALUES (?, ?, ?)",
                (q_text, options, correct),
            )
        conn.commit()
    conn.close()


# -----------------------------
# Utility helpers
# -----------------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def human_time_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# -----------------------------
# Bot Handlers
# -----------------------------
# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "Men @Ustozgayordambot — o'qituvchilar uchun yordamchi botman.\n"
        "Quyidagi buyruqlardan foydalaning:\n\n"
        "/register — ro'yxatdan o'tish\n"
        "/materials — dars materiallari\n"
        "/quiz — qisqa test\n"
        "/attendance — hozirlikni belgilash\n"
        "/ask — savol yuborish adminlarga\n"
        "/help — qo'shimcha yordam\n"
    )
    await update.message.reply_text(text)


# /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Qo'llanma:\n"
        "/register — ro'yxatdan o'ting (kirish uchun kerak)\n"
        "/materials — mavjud materiallar ro'yxati\n"
        "/quiz — qisqa interaktiv test\n"
        "/attendance — bugungi darsda ishtirok etganingizni belgilash\n"
        "/ask <savol> — savolingizni adminlarga yuboradi\n\n"
        "Adminlar: /broadcast <xabar> , /stats"
    )


# /register
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    registered_at = human_time_now()
    try:
        db_execute(
            "INSERT OR IGNORE INTO users (tg_id, name, registered_at) VALUES (?, ?, ?)",
            (tg_id, name, registered_at),
        )
        await update.message.reply_text(
            "Siz ro‘yxatdan o‘tdingiz ✅\nEndi /materials va /quiz funksiyalaridan foydalanishingiz mumkin."
        )
    except Exception as e:
        logger.exception("Register error")
        await update.message.reply_text("Ro'yxatdan o'tishda xatolik yuz berdi.")


# /materials
async def materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # List files from MATERIALS_FOLDER
    if not os.path.exists(MATERIALS_FOLDER):
        os.makedirs(MATERIALS_FOLDER)
    files = os.listdir(MATERIALS_FOLDER)
    if not files:
        await update.message.reply_text(
            "Materiallar katalogi bo'sh. Adminlar hali hech nima yuborishmagan."
        )
        return
    buttons = [
        [InlineKeyboardButton(text=f, callback_data=f"material__{f}")] for f in files
    ]
    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Mavjud materiallar ro'yxati:", reply_markup=kb)


# callback for material download
async def callback_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("material__"):
        filename = data.split("__", 1)[1]
        path = os.path.join(MATERIALS_FOLDER, filename)
        if os.path.exists(path):
            await query.message.reply_document(document=open(path, "rb"))
        else:
            await query.message.reply_text("Fayl topilmadi yoki o'chirilgan.")


# /attendance - mark present
async def attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    date = datetime.utcnow().strftime("%Y-%m-%d")
    note = "present"
    # prevent duplicate for today
    existing = db_execute(
        "SELECT id FROM attendance WHERE tg_id=? AND date=?", (tg_id, date), fetch=True
    )
    if existing:
        await update.message.reply_text("Siz allaqachon bugun hozirlikni belgilagansiz ✅")
        return
    db_execute(
        "INSERT INTO attendance (tg_id, date, note) VALUES (?, ?, ?)", (tg_id, date, note)
    )
    await update.message.reply_text("Hozirlik belgilandi — rahmat! ✨")


# /stats (admin)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Bu buyruq faqat adminlar uchun.")
        return
    # get user count and today's attendance
    users = db_execute("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    att = db_execute("SELECT COUNT(*) FROM attendance WHERE date=?", (today,), fetch=True)[0][0]
    await update.message.reply_text(f"Ro'yxatdan o'tganlar: {users}\nBugungi hozirlik: {att}")


# /ask <question>
async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Iltimos: /ask <savolingiz> shaklida yuboring.")
        return
    question = parts[1].strip()
    db_execute(
        "INSERT INTO asks (tg_id, question, asked_at) VALUES (?, ?, ?)",
        (tg_id, question, human_time_now()),
    )
    await update.message.reply_text("Savolingiz adminlarga yuborildi — tez orada javob berishadi.")
    # Forward to admins
    for adm in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=adm,
                text=f"Yangi savol from @{user.username or user.id}:\n\n{question}\n\nID: {tg_id}",
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {adm}: {e}")


# Broadcast (admin)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Bu buyruq faqat adminlar uchun.")
        return
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Iltimos: /broadcast <xabar> shaklida yuboring.")
        return
    message = parts[1].strip()
    users = db_execute("SELECT tg_id FROM users", fetch=True)
    count = 0
    for (tg_id,) in users:
        try:
            await context.bot.send_message(chat_id=tg_id, text=message)
            count += 1
        except Exception as e:
            logger.warning(f"Failed to send to {tg_id}: {e}")
    await update.message.reply_text(f"Xabar yuborildi: {count} foydalanuvchiga.")


# -----------------------------
# Quiz flow (ConversationHandler)
# -----------------------------
QUIZ_Q, QUIZ_ANSWER = range(2)


def get_all_questions() -> List[Dict]:
    rows = db_execute("SELECT id, q_text, options, correct_index FROM questions", fetch=True)
    questions = []
    for r in rows:
        qid, q_text, options, correct = r
        opts = options.split("|")
        questions.append({"id": qid, "q_text": q_text, "options": opts, "correct": int(correct)})
    return questions


async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ensure user registered
    user = update.effective_user
    reg = db_execute("SELECT id FROM users WHERE tg_id=?", (user.id,), fetch=True)
    if not reg:
        await update.message.reply_text("Iltimos avval /register bilan ro'yxatdan o'ting.")
        return ConversationHandler.END

    questions = get_all_questions()
    if not questions:
        await update.message.reply_text("Hozircha test savollari mavjud emas.")
        return ConversationHandler.END

    # store quiz state in user_data
    context.user_data["quiz"] = {
        "questions": questions,
        "index": 0,
        "score": 0,
        "total": len(questions),
    }
    # send first question
    q = questions[0]
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(opt, callback_data=f"quiz__{i}")] for i, opt in enumerate(q["options"])]
    )
    await update.message.reply_text(f"1/{len(questions)}: {q['q_text']}", reply_markup=kb)
    return QUIZ_ANSWER


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("quiz__"):
        return
    selected_index = int(data.split("__", 1)[1])
    quiz_state = context.user_data.get("quiz")
    if not quiz_state:
        await query.message.reply_text("Quizni boshlash uchun /quiz bosing.")
        return ConversationHandler.END
    idx = quiz_state["index"]
    q = quiz_state["questions"][idx]
    correct = q["correct"]
    if selected_index == correct:
        quiz_state["score"] += 1
        await query.message.reply_text("To'g'ri ✅")
    else:
        await query.message.reply_text(f"Noto'g'ri ❌. To'g'ri javob: {q['options'][correct]}")

    # next
    quiz_state["index"] += 1
    if quiz_state["index"] >= quiz_state["total"]:
        # finish
        score = quiz_state["score"]
        total = quiz_state["total"]
        # save result
        db_execute(
            "INSERT INTO quiz_results (tg_id, score, total, taken_at) VALUES (?, ?, ?, ?)",
            (update.effective_user.id, score, total, human_time_now()),
        )
        await query.message.reply_text(f"Test tugadi — Siz: {score}/{total}")
        context.user_data.pop("quiz", None)
        return ConversationHandler.END
    else:
        next_q = quiz_state["questions"][quiz_state["index"]]
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(opt, callback_data=f"quiz__{i}")] for i, opt in enumerate(next_q["options"])]
        )
        await query.message.reply_text(
            f"{quiz_state['index']+1}/{quiz_state['total']}: {next_q['q_text']}", reply_markup=kb
        )
        return QUIZ_ANSWER


# fallback
async def quiz_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("quiz", None)
    await update.message.reply_text("Quiz bekor qilindi.")
    return ConversationHandler.END


# Handler to receive files from admin and save as materials
async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Fayl qabul qilindi — ammo materiallarni yuklash faqat adminlar uchun.")
        return
    # ensure folder
    if not os.path.exists(MATERIALS_FOLDER):
        os.makedirs(MATERIALS_FOLDER)
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Fayl topilmadi.")
        return
    file_name = doc.file_name
    file = await context.bot.get_file(doc.file_id)
    out_path = os.path.join(MATERIALS_FOLDER, file_name)
    await file.download_to_drive(out_path)
    await update.message.reply_text(f"Fayl saqlandi: {file_name}")


# unknown messages
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kechirasiz, bu buyruq tushunilmadi. /help ni bosing.")


# -----------------------------
# Main
# -----------------------------
def main():
    # init db & seed
    init_db()
    seed_questions()

    # Build app
    app = ApplicationBuilder().token(TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("materials", materials))
    app.add_handler(CallbackQueryHandler(callback_materials, pattern=r"^material__"))
    app.add_handler(CommandHandler("attendance", attendance))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))

    # Document receiver (admin uploads)
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, receive_document))

    # Quiz conversation
    quiz_conv = ConversationHandler(
        entry_points=[CommandHandler("quiz", quiz_start)],
        states={
            QUIZ_ANSWER: [CallbackQueryHandler(quiz_answer_callback, pattern=r"^quiz__")],
        },
        fallbacks=[CommandHandler("cancel", quiz_cancel)],
        per_user=True,
    )
    app.add_handler(quiz_conv)

    # Unknown
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown))

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
