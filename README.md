pip install pyTelegramBotAPI
import telebot
from telebot import types

# === SHU YERNI O'ZGARTIRASIZ ===
TOKEN = "8101415283:AAFUhlvQ8vJf6dUXh2X4hSJQx09CbLDQNIM"   # BotFather bergan token
ADMIN_CHAT_ID = 6690155099                 # O'zingizning Telegram ID'ingiz
# =================================

bot = telebot.TeleBot(TOKEN)


# /start komandasi
@bot.message_handler(commands=['start'])
def start(message):
    text = (
        "Assalomu alaykum! 👋\n"
        "Bu *HUJJAT ALOQA BOT*.\n\n"
        "Siz bu yerga:\n"
        "📄 Hujjat (doc, pdf, ppt...)\n"
        "🖼 Rasm / skrinshot\n"
        "💬 Oddiy matn xabar\n"
        "yuborsangiz, ular avtomatik ravishda mas’ul shaxsga yetkaziladi.\n\n"
        "✅ Hujjatni yoki xabaringizni yuborishingiz mumkin."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# Foydalanuvchi hujjat yuborganda
@bot.message_handler(content_types=['document'])
def handle_document(message):
    # foydalanuvchi haqida qisqacha maʼlumot
    caption = (
        f"📄 Yangi hujjat!\n\n"
        f"👤 Foydalanuvchi: {message.from_user.first_name} "
        f"(@{message.from_user.username})\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"📎 Hujjat nomi: {message.document.file_name}"
    )

    # hujjatni admin chatiga forward qilish
    bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=caption)

    # foydalanuvchiga javob
    bot.reply_to(message, "✅ Hujjatingiz mas’ul shaxsga yuborildi.")


# Foydalanuvchi rasm yuborganda
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    caption = (
        f"🖼 Yangi rasm!\n\n"
        f"👤 Foydalanuvchi: {message.from_user.first_name} "
        f"(@{message.from_user.username})\n"
        f"🆔 ID: {message.from_user.id}"
    )

    # eng sifatli rasmini olamiz (oxirgisi eng kattasi bo'ladi)
    photo = message.photo[-1]
    bot.send_photo(ADMIN_CHAT_ID, photo.file_id, caption=caption)

    bot.reply_to(message, "✅ Rasmingiz mas’ul shaxsga yuborildi.")


# Foydalanuvchi oddiy xabar yuborganda
@bot.message_handler(content_types=['text'])
def handle_text(message):
    text_to_admin = (
        "💬 Yangi matnli xabar!\n\n"
        f"👤 Foydalanuvchi: {message.from_user.first_name} "
        f"(@{message.from_user.username})\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"✉️ Xabar matni:\n{message.text}"
    )

    bot.send_message(ADMIN_CHAT_ID, text_to_admin)
    bot.reply_to(message, "✅ Xabaringiz mas’ul shaxsga yuborildi.")


# Test uchun /id komandasi (o'zingizning ID ni ko'rish uchun)
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.reply_to(message, f"Sizning chat ID'ingiz: `{message.chat.id}`", parse_mode="Markdown")


# Botni doimiy ishlatish
print("Bot ishga tushdi...")
bot.infinity_polling()
