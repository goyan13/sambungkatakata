from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

import os
import uuid

from game import show_room
from game import (
    rooms, waiting_player, public_room_id,
    start_game, handle_word
)

TOKEN = os.getenv("BOT_TOKEN")

app = ApplicationBuilder().token(TOKEN).build()

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
    """🎮 Sambung Kata

📜 Cara Bermain:
- Sambung kata dari huruf terakhir
- Contoh: ikan → nasi → ilmu → unta
- Tidak boleh mengulang kata
- Waktu 15 detik per giliran

👇 Pilih mode:""",
    reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CREATE PRIVATE ROOM
# =========================
async def create_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = str(uuid.uuid4())[:4]

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
        f"🔐 Room dibuat!\nKode: {code}"
    )

    await show_room(context, rooms[code], code)

# =========================
# JOIN PRIVATE ROOM
# =========================
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

    for p in room["players"]:
        if p["id"] == user.id:
            await update.message.reply_text("Kamu sudah di room!")
            return

    room["players"].append({
        "id": user.id,
        "name": user.first_name,
        "chat_id": user.id
    })

    await update.message.reply_text(f"Masuk room {code}")

    await show_room(context, room, code)

# =========================
# BUTTON HANDLER
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_player, public_room_id

    query = update.callback_query
    await query.answer()

    user = query.from_user

    # 🔐 PRIVATE INFO
    if query.data == "private":
        await context.bot.send_message(
            chat_id=user.id,
            text="Gunakan:\n/create\n/join KODE"
        )
        return

    # ▶️ START GAME
    if query.data.startswith("start_"):
        code = query.data.split("_")[1]
        room = rooms.get(code)

        if not room:
            return

        if len(room["players"]) < 2:
            await query.answer("Butuh 2 player!", show_alert=True)
            return

        room["started"] = True
        await start_game(context, code)
        return

    # ❌ LEAVE ROOM
    if query.data.startswith("leave_"):
        code = query.data.split("_")[1]
        room = rooms.get(code)

        if not room:
            return

        room["players"] = [p for p in room["players"] if p["id"] != user.id]

        await context.bot.send_message(
            chat_id=user.id,
            text="Kamu keluar dari room"
        )

        if not room["players"]:
            rooms.pop(code)
            return

        await show_room(context, room, code)
        return

    # ⚡ QUICK MATCH
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

    # 👥 PUBLIC ROOM
    elif query.data == "public":
        if public_room_id is None or public_room_id not in rooms:
            public_room_id = str(uuid.uuid4())

            rooms[public_room_id] = {
                "players": [],
                "turn": 0,
                "current_word": "",
                "used_words": [],
                "started": False
            }

        room = rooms[public_room_id]

        for p in room["players"]:
            if p["id"] == user.id:
                await query.answer("Kamu sudah join!")
                return

        room["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chat_id": user.id
        })

        await query.edit_message_text(
            f"👥 Room Publik\nPlayer: {len(room['players'])}"
        )

        if len(room["players"]) >= 2 and not room["started"]:
            room["started"] = True
            await start_game(context, public_room_id)

# =========================
# HANDLER
# =========================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("create", create_private))
app.add_handler(CommandHandler("join", join_private))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

print("Bot jalan...")
app.run_polling()
