from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

import os
import logging
import random
import uuid
import json

# =========================
# CONFIG
# =========================
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN belum diset!")

TURN_TIME = 15
MAX_PLAYER = 5

app = ApplicationBuilder().token(TOKEN).build()

# =========================
# GLOBAL STATE
# =========================
rooms = {}
waiting_player = None
public_room_id = None

DATA_FILE = "data.json"
leaderboard = {}

# =========================
# WORDS
# =========================
def load_words():
    try:
        with open("words.txt", "r", encoding="utf-8") as f:
            return set(w.strip().lower() for w in f if w.strip())
    except:
        return {
            "kucing","gajah","harimau","ular","rumah","mobil",
            "makan","minum","ikan","nasi","air","roti",
            "lampu","lemari","listrik","lumba","laut","langit"
        }

VALID_WORDS = load_words()

# =========================
# SAVE / LOAD
# =========================
def load_data():
    global leaderboard
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            leaderboard = data.get("leaderboard", {})
    except:
        leaderboard = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"leaderboard": leaderboard}, f)

load_data()

# =========================
# HELPER
# =========================
async def broadcast(context, room, text):
    for p in room["players"]:
        try:
            await context.bot.send_message(
                chat_id=p["chat_id"],
                text=text,
                parse_mode="Markdown"
            )
        except:
            pass


def get_player(room, user_id):
    for p in room["players"]:
        if p["id"] == user_id:
            return p
    return None


def add_score(user_id, name):
    uid = str(user_id)
    if uid not in leaderboard:
        leaderboard[uid] = {"name": name, "score": 0}

    leaderboard[uid]["score"] += 1
    save_data()


def suggest_word(last_letter):
    for w in VALID_WORDS:
        if w.startswith(last_letter):
            return w
    return None

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ Quick Match", callback_data="quick")],
        [InlineKeyboardButton("👥 Room Publik", callback_data="public")],
        [InlineKeyboardButton("🔐 Room Private", callback_data="private")]
    ]

    await update.message.reply_text(
        "🎮 *Sambung Kata*\n\nPilih mode:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# PRIVATE ROOM
# =========================
async def create_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = str(random.randint(1000, 9999))
    user = update.message.from_user

    rooms[code] = {
        "players": [{
            "id": user.id,
            "name": user.first_name,
            "chat_id": user.id
        }],
        "turn": 0,
        "current_word": "",
        "used_words": [],
        "started": False
    }

    await update.message.reply_text(
        f"🔐 Room dibuat!\nKode: {code}\nGunakan /join {code}"
    )


async def join_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text("Masukkan kode room!")
        return

    code = args[0]

    if code not in rooms:
        await update.message.reply_text("Room tidak ditemukan!")
        return

    room = rooms[code]
    user = update.message.from_user

    if get_player(room, user.id):
        await update.message.reply_text("Kamu sudah di room!")
        return

    room["players"].append({
        "id": user.id,
        "name": user.first_name,
        "chat_id": user.id
    })

    await update.message.reply_text(f"Masuk room {code}")

    if len(room["players"]) >= 2 and not room["started"]:
        room["started"] = True
        await start_game(context, code)

# =========================
# BUTTON
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_player, public_room_id

    query = update.callback_query
    await query.answer()

    user = query.from_user

    if query.data == "private":
        await context.bot.send_message(
            chat_id=user.id,
            text="Gunakan /create untuk buat room private"
        )
        return

    if query.data == "quick":

        if waiting_player is None:
            waiting_player = {
                "id": user.id,
                "name": user.first_name,
                "chat_id": user.id
            }
            await query.edit_message_text("⏳ Menunggu lawan...")
        else:
            room_id = str(uuid.uuid4())

            rooms[room_id] = {
                "players": [
                    waiting_player,
                    {
                        "id": user.id,
                        "name": user.first_name,
                        "chat_id": user.id
                    }
                ],
                "turn": 0,
                "current_word": "",
                "used_words": [],
                "started": True
            }

            waiting_player = None

            await query.edit_message_text("🎉 Lawan ditemukan!")
            await start_game(context, room_id)

    elif query.data == "public":

        if public_room_id is None or public_room_id not in rooms or rooms[public_room_id]["started"]:
            public_room_id = str(uuid.uuid4())

            rooms[public_room_id] = {
                "players": [],
                "turn": 0,
                "current_word": "",
                "used_words": [],
                "started": False
            }

        room = rooms[public_room_id]

        if get_player(room, user.id):
            await query.answer("Kamu sudah join!")
            return

        room["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chat_id": user.id
        })

        await query.edit_message_text(
            f"👥 Room Publik\nPlayer: {len(room['players'])}/{MAX_PLAYER}"
        )

        if len(room["players"]) >= 2 and not room["started"]:
            room["started"] = True
            await start_game(context, public_room_id)

# =========================
# START GAME
# =========================
async def start_game(context, room_id):
    room = rooms[room_id]

    first_word = random.choice(list(VALID_WORDS))

    room["current_word"] = first_word
    room["used_words"] = [first_word]
    room["turn"] = 0

    players = "\n".join([p["name"] for p in room["players"]])

    await broadcast(
        context,
        room,
        f"🚀 *Game dimulai!*\n\nPemain:\n{players}\n\nKata: *{first_word}*\n\nGiliran: {room['players'][0]['name']}"
    )

    await start_turn_timer(context, room_id)

# =========================
# HANDLE WORD
# =========================
async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.lower().strip()

    if not text or len(text) < 2:
        return

    for room_id, room in rooms.items():
        player = get_player(room, user.id)

        if not player:
            continue

        current = room["players"][room["turn"]]

        if user.id != current["id"]:
            continue

        last = room["current_word"]

        # ANTI STUCK
        if not any(w.startswith(last[-1]) for w in VALID_WORDS):
            await broadcast(context, room, "⚠️ Tidak ada kata lanjutan, game di-reset!")
            await start_game(context, room_id)
            return

        if text not in VALID_WORDS:
            await update.message.reply_text("❌ Kata tidak valid!")
            return

        if text[0] != last[-1]:
            suggestion = suggest_word(last[-1])
            await update.message.reply_text(
                f"❌ Huruf salah!\nContoh: {suggestion}"
            )
            return

        if text in room["used_words"]:
            await update.message.reply_text("❌ Sudah dipakai!")
            return

        room["current_word"] = text
        room["used_words"].append(text)

        add_score(user.id, user.first_name)

        room["turn"] = (room["turn"] + 1) % len(room["players"])
        next_p = room["players"][room["turn"]]

        await broadcast(
            context,
            room,
            f"✅ *{player['name']}*: {text}\nGiliran: {next_p['name']}"
        )

        await start_turn_timer(context, room_id)
        return

# =========================
# LEADERBOARD
# =========================
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("Belum ada skor!")
        return

    text = "🏆 Leaderboard\n\n"
    sorted_lb = sorted(leaderboard.values(), key=lambda x: x["score"], reverse=True)

    for i, p in enumerate(sorted_lb[:10], 1):
        text += f"{i}. {p['name']} - {p['score']}\n"

    await update.message.reply_text(text)

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

    if not room or not room.get("started"):
        return

    current = room["players"][room["turn"]]

    room["turn"] = (room["turn"] + 1) % len(room["players"])
    next_p = room["players"][room["turn"]]

    await broadcast(
        context,
        room,
        f"⏰ {current['name']} kehabisan waktu!\nGiliran: {next_p['name']}"
    )

    await start_turn_timer(context, room_id)

# =========================
# HANDLER
# =========================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("create", create_private))
app.add_handler(CommandHandler("join", join_private))
app.add_handler(CommandHandler("rank", show_leaderboard))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

print("Bot jalan...")
app.run_polling()
