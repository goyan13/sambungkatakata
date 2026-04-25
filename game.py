import random

from utils import broadcast, get_player, add_score, suggest_word, VALID_WORDS

rooms = {}
waiting_player = None
public_room_id = None

TURN_TIME = 15
MAX_PLAYER = 5

# =========================
# START GAME
# =========================
async def start_game(context, room_id):
    room = rooms.get(room_id)

    if not room or not room["players"]:
        return

    if not VALID_WORDS:
        await broadcast(context, room, "❌ Database kata kosong!")
        return

    first_word = random.choice(list(VALID_WORDS))

    room["current_word"] = first_word
    room["used_words"] = [first_word]
    room["turn"] = 0
    room["started"] = True

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
async def handle_word(update, context):
    user = update.message.from_user
    text = update.message.text.lower().strip()

    if not text or len(text) < 2:
        return

    for room_id, room in rooms.items():
        if not room.get("started"):
            continue

        player = get_player(room, user.id)
        if not player:
            continue

        if not room["players"]:
            return

        current = room["players"][room["turn"]]

        if user.id != current["id"]:
            return

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
            await update.message.reply_text(f"❌ Salah! Contoh: {suggestion}")
            return

        if text in room["used_words"]:
            await update.message.reply_text("❌ Sudah dipakai!")
            return

        # UPDATE GAME
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

    if not room["players"]:
        rooms.pop(room_id, None)
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
# ROOM UI
# =========================
async def show_room(context, room, code):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not room["players"]:
        return

    players = "\n".join([f"- {p['name']}" for p in room["players"]])

    keyboard = [
        [InlineKeyboardButton("▶️ Start Game", callback_data=f"start_{code}")],
        [InlineKeyboardButton("❌ Keluar", callback_data=f"leave_{code}")]
    ]

    for p in room["players"]:
        try:
            await context.bot.send_message(
                chat_id=p["chat_id"],
                text=f"🔐 Room {code}\n\n👥 Player:\n{players}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
