from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import logging

# Logging biar gampang debug di Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN belum diset di Railway Variables!")
print("TOKEN", TOKEN)

app = ApplicationBuilder().token(TOKEN).build()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ Quick Match", callback_data="quick")],
        [InlineKeyboardButton("👥 Buat Room", callback_data="create")]
    ]

    await update.message.reply_text(
        "🎮 Sambung Kata\n\nPilih mode:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# tombol handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "quick":
        await query.edit_message_text("⏳ Mencari lawan...")

    elif query.data == "create":
        await query.edit_message_text("👥 Mode room (coming soon)")

# register handler
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

# run bot

app.run_polling()

import random

rooms = {}

# =========================
# START GAME
# =========================
async def start_game(update, context, room_id):
    room = rooms[room_id]

    await start_turn_timer(context, room_id)

    words = ["kucing", "mobil", "rumah", "makan", "minum"]
    first_word = random.choice(words)

    room["current_word"] = first_word
    room["used_words"] = [first_word]
    room["turn"] = 0

    await context.bot.send_message(
        chat_id=room["chat_id"],
        text=f"🚀 Game dimulai!\n\nKata awal: *{first_word}*\n\nGiliran: {room['players'][0]['name']}",
        parse_mode="Markdown"
    )
    

# =========================
# HANDLE KATA
# =========================
async def handle_word(update, context):
    await start_turn_timer(context, room_id)

    user = update.message.from_user
    text = update.message.text.lower()


    # cari room user
    for room_id, room in rooms.items():
        player_ids = [p["id"] for p in room["players"]]

        if user.id in player_ids:
            turn_player = room["players"][room["turn"]]

            # cek giliran
            if user.id != turn_player["id"]:
                return

            last_word = room["current_word"]

            # validasi sambung kata
            if text[0] != last_word[-1]:
                await update.message.reply_text("❌ Huruf tidak cocok!")
                return

            # cek sudah dipakai
            if text in room["used_words"]:
                await update.message.reply_text("❌ Kata sudah dipakai!")
                return

            # valid
            room["current_word"] = text
            room["used_words"].append(text)

            await start_turn_timer(context, room_id)

            # pindah turn
            room["turn"] = (room["turn"] + 1) % len(room["players"])
            next_player = room["players"][room["turn"]]

            await update.message.reply_text(
                f"✅ Benar!\nKata sekarang: {text}\n\nGiliran: {next_player['name']}"
            )
            return

from telegram.ext import MessageHandler, filters

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))


TURN_TIME = 15  # detik
async def start_turn_timer(context, room_id):
    job_name = f"timer_{room_id}"

    # hapus timer lama
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    # buat timer baru
    context.job_queue.run_once(
        timeout_turn,
        TURN_TIME,
        data={"room_id": room_id},
        name=job_name
    )

async def timeout_turn(context):
    job_data = context.job.data
    room_id = job_data["room_id"]

    room = rooms.get(room_id)
    if not room:
        return

    current_player = room["players"][room["turn"]]

    # pindah giliran
    room["turn"] = (room["turn"] + 1) % len(room["players"])
    next_player = room["players"][room["turn"]]

    await context.bot.send_message(
        chat_id=room["chat_id"],
        text=f"⏰ {current_player['name']} kehabisan waktu!\n\nGiliran: {next_player['name']}"
    )

