from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
import os, logging, random, uuid

# =========================
# CONFIG
# =========================
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN belum diset!")

TURN_TIME = 15

app = ApplicationBuilder().token(TOKEN).build()

# =========================
# GLOBAL
# =========================
rooms = {}
waiting_player = None
public_room_id = None
MAX_PLAYER = 5

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ Quick Match", callback_data="quick")],
        [InlineKeyboardButton("👥 Room Publik", callback_data="create")]
    ]

    await update.message.reply_text(
        "🎮 Sambung Kata\n\nPilih mode:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# BUTTON
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_player, public_room_id

    query = update.callback_query
    await query.answer()

    user = query.from_user

    # ================= QUICK MATCH =================
    if query.data == "quick":

        if waiting_player is None:
            waiting_player = {
                "id": user.id,
                "name": user.first_name,
                "chat_id": query.message.chat_id
            }
            await query.edit_message_text("⏳ Menunggu lawan...")

        else:
            room_id = str(uuid.uuid4())

            player1 = waiting_player
            player2 = {
                "id": user.id,
                "name": user.first_name,
                "chat_id": query.message.chat_id
            }

            rooms[room_id] = {
                "players": [player1, player2],
                "turn": 0,
                "current_word": "",
                "used_words": [],
                "chat_id": player1["chat_id"],
                "started": False
            }

            waiting_player = None

            await query.edit_message_text("🎉 Lawan ditemukan!")
            await start_game(context, room_id)

    # ================= ROOM PUBLIK =================
    elif query.data == "create":

        if public_room_id is None:
            public_room_id = str(uuid.uuid4())

            rooms[public_room_id] = {
                "players": [],
                "turn": 0,
                "current_word": "",
                "used_words": [],
                "chat_id": query.message.chat_id,
                "started": False
            }

        room = rooms[public_room_id]

        # sudah join?
        if any(p["id"] == user.id for p in room["players"]):
            await query.answer("Kamu sudah join!")
            return

        # tambah player
        room["players"].append({
            "id": user.id,
            "name": user.first_name
        })

        await query.edit_message_text(
            f"👥 Room Publik\n\nPlayer: {len(room['players'])}/{MAX_PLAYER}"
        )

        # auto start
        if len(room["players"]) >= 2 and not room["started"]:
            room["started"] = True
            await start_game(context, public_room_id)

# =========================
# START GAME
# =========================
async def start_game(context, room_id):
    room = rooms[room_id]

    words = ["kucing", "mobil", "rumah", "makan", "minum"]
    first_word = random.choice(words)

    room["current_word"] = first_word
    room["used_words"] = [first_word]
    room["turn"] = 0

    player_names = "\n".join([p["name"] for p in room["players"]])

    await start_turn_timer(context, room_id)

    await context.bot.send_message(
        chat_id=room["chat_id"],
        text=f"🚀 Game dimulai!\n\nPemain:\n{player_names}\n\nKata: *{first_word}*\n\nGiliran: {room['players'][0]['name']}",
        parse_mode="Markdown"
    )

# =========================
# HANDLE WORD
# =========================
async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.lower().strip()

    if not text or len(text) < 2:
        return

    for room_id, room in rooms.items():
        if user.id in [p["id"] for p in room["players"]]:

            turn_player = room["players"][room["turn"]]

            if user.id != turn_player["id"]:
                return

            last_word = room["current_word"]

            if text[0] != last_word[-1]:
                await update.message.reply_text("❌ Huruf salah!")
                return

            if text in room["used_words"]:
                await update.message.reply_text("❌ Sudah dipakai!")
                return

            room["current_word"] = text
            room["used_words"].append(text)

            await start_turn_timer(context, room_id)

            room["turn"] = (room["turn"] + 1) % len(room["players"])
            next_player = room["players"][room["turn"]]

            await update.message.reply_text(
                f"✅ {text}\nGiliran: {next_player['name']}"
            )
            return

# =========================
# TIMER
# =========================
async def start_turn_timer(context, room_id):
    job_name = f"timer_{room_id}"

    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()

    context.job_queue.run_once(
        timeout_turn,
        TURN_TIME,
        data={"room_id": room_id},
        name=job_name
    )

async def timeout_turn(context):
    room_id = context.job.data["room_id"]
    room = rooms.get(room_id)

    if not room:
        return

    current = room["players"][room["turn"]]

    room["turn"] = (room["turn"] + 1) % len(room["players"])
    next_p = room["players"][room["turn"]]

    await context.bot.send_message(
        chat_id=room["chat_id"],
        text=f"⏰ {current['name']} kehabisan waktu!\nGiliran: {next_p['name']}"
    )

# =========================
# HANDLER
# =========================
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

print("Bot jalan...")
app.run_polling()
