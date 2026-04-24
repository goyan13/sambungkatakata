import json

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
            "makan","minum","ikan","nasi","air","roti"
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


load_data()
