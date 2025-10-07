# app.py
from flask import Flask, render_template, request, jsonify
import csv, random, re, uuid, os
import typesense
from flask_socketio import SocketIO, emit, join_room, leave_room

# --- Config & load arc order ---
with open("Arcs.txt", encoding="utf-8") as f:
    arcs_order = [line.strip() for line in f if line.strip()]

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "replace-with-a-secret")

# --- Typesense client (configure with your credentials) ---
typesense_client = typesense.Client({
    "nodes": [{
        "host": "apn0q798izyjv4u3p-1.a1.typesense.net",
        "port": "443",
        "protocol": "https"
    }],
    "api_key": "59gbcoo05qOMzKKqQWOGXVJRu6CRmrLt",
    "connection_timeout_seconds": 2
})

# --- Character class & loader ---
class Character:
    def __init__(self, name, first_arc, affiliation, bounty, height, devil_fruit_type, haki, gender):
        self.name = name
        self.first_arc = first_arc
        self.affiliation = affiliation
        # Ensure numeric types are safe even for small test rows
        try:
            self.bounty = int(bounty)
        except:
            self.bounty = 0
        try:
            self.height = float(height)
        except:
            self.height = 0.0
        self.devil_fruit_type = devil_fruit_type
        self.haki = set(h.strip() for h in haki.split(";") if h.strip() and h.strip().lower() != "none")
        self.gender = gender

def load_characters(filename="Characters.txt"):
    characters = []
    with open(filename, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            characters.append(Character(
                row.get("name","").strip(),
                row.get("first_arc","").strip(),
                row.get("affiliation","").strip(),
                row.get("bounty","0").strip(),
                row.get("height","0").strip(),
                row.get("devil_fruit_type","").strip(),
                row.get("haki","").strip(),
                row.get("gender","").strip()
            ))
    return characters

characters = load_characters()
# fallback single-player target
target = random.choice(characters) if characters else None

# --- Typesense schema & upsert (idempotent-ish) ---
character_schema = {
    "name": "characters",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "first_arc", "type": "string", "facet": True},
        {"name": "affiliation", "type": "string", "facet": True},
        {"name": "bounty", "type": "int64"},
        {"name": "height", "type": "float"},
        {"name": "devil_fruit_type", "type": "string", "facet": True},
        {"name": "haki", "type": "string[]", "facet": True}
    ],
    "default_sorting_field": "bounty"
}

try:
    typesense_client.collections.create(character_schema)
    print("✅ Collection created")
except Exception as e:
    print("⚠️ Collection exists or failed:", e)

# upload documents (upsert)
documents = []
for c in characters:
    documents.append({
        "id": c.name.lower().replace(" ", "_"),
        "name": c.name,
        "first_arc": c.first_arc,
        "affiliation": c.affiliation,
        "bounty": c.bounty,
        "height": c.height,
        "devil_fruit_type": c.devil_fruit_type,
        "haki": list(c.haki)
    })

try:
    typesense_client.collections["characters"].documents.import_(documents, {"action": "upsert"})
    print("✅ Characters upserted")
except Exception as e:
    print("⚠️ Import failed:", e)

# --- Comparison logic (single-player guess feedback) ---
def compare_characters(target, guess):
    feedback = {}
    feedback["name"] = {"value": guess.name, "status": "neutral"}
    feedback["gender"] = {"value": guess.gender, "status": "correct" if target.gender == guess.gender else "incorrect"}

    if target.first_arc == guess.first_arc:
        status = "correct"
    else:
        try:
            target_idx = arcs_order.index(target.first_arc)
            guess_idx = arcs_order.index(guess.first_arc)
            status = "later" if target_idx > guess_idx else "earlier"
        except ValueError:
            status = "incorrect"
    feedback["first_arc"] = {"value": guess.first_arc, "status": status}

    feedback["affiliation"] = {"value": guess.affiliation, "status": "correct" if target.affiliation == guess.affiliation else "incorrect"}
    feedback["bounty"] = {"value": guess.bounty, "status": "correct" if target.bounty == guess.bounty else ("higher" if target.bounty > guess.bounty else "lower")}
    feedback["height"] = {"value": guess.height, "status": "correct" if target.height == guess.height else ("higher" if target.height > guess.height else "lower")}
    feedback["devilfruit"] = {"value": guess.devil_fruit_type, "status": "correct" if target.devil_fruit_type == guess.devil_fruit_type else "incorrect"}
    if target.haki == guess.haki:
        status = "correct"
    elif guess.haki & target.haki:
        status = "partial"
    else:
        status = "incorrect"
    feedback["haki"] = {"value": ", ".join(guess.haki) if guess.haki else "None", "status": status}
    return feedback

# ---------------------- Socket.IO setup ----------------------
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Rooms structure
rooms = {}  # {room_id: {owner, players: {name: {score, guessed:set, bonus_given}}, mode, timer, target, started}}

ATTRIBUTES = ["gender", "first_arc", "affiliation", "bounty", "height", "devil_fruit_type", "haki"]

def pick_random_target():
    return random.choice(characters) if characters else None

# ---------------------- Socket events ----------------------
@socketio.on("create_room")
def handle_create_room(data):
    player = data.get("player")
    if not player:
        emit("error", {"msg": "Player name required"})
        return
    mode = data.get("mode", "timed")  # 'timed' or 'first_to_guess' (or 'first_to_complete' in older code)
    timer = int(data.get("timer", 120))
    room_id = uuid.uuid4().hex[:6]

    rooms[room_id] = {
        "owner": player,
        "players": {},
        "mode": mode,
        "timer": timer,
        "target": pick_random_target(),
        "started": False
    }
    rooms[room_id]["players"][player] = {"score": 0, "guessed": set(), "bonus_given": False}
    join_room(room_id)
    emit("room_joined", {"room_id": room_id, "owner": player, "mode": mode, "timer": timer, "players": list(rooms[room_id]["players"].keys())}, room=room_id)

@socketio.on("join_room")
def handle_join_room(data):
    room_id = data.get("room_id")
    player = data.get("player")
    if not player or not room_id:
        emit("error", {"msg": "player and room_id required"})
        return
    if room_id not in rooms:
        emit("error", {"msg": "Room not found"})
        return
    if player in rooms[room_id]["players"]:
        emit("error", {"msg": "Name already taken in room, choose another"})
        return
    rooms[room_id]["players"][player] = {"score": 0, "guessed": set(), "bonus_given": False}
    join_room(room_id)
    emit("player_joined", {"player": player, "players": list(rooms[room_id]["players"].keys())}, room=room_id)

@socketio.on("set_mode")
def handle_set_mode(data):
    room_id = data.get("room_id")
    mode = data.get("mode")
    timer = int(data.get("timer", 120))
    if room_id in rooms:
        rooms[room_id]["mode"] = mode
        rooms[room_id]["timer"] = timer
        emit("mode_set", {"mode": mode, "timer": timer}, room=room_id)

@socketio.on("start_game")
def handle_start_game(data):
    room_id = data.get("room_id")
    player = data.get("player")
    if room_id not in rooms:
        emit("error", {"msg": "Room not found"})
        return
    if rooms[room_id]["owner"] != player:
        emit("error", {"msg": "Only the owner can start the game"})
        return

    rooms[room_id]["started"] = True
    # reset per-player guessed sets and scores
    for name, p in rooms[room_id]["players"].items():
        p["guessed"] = set()
        p["bonus_given"] = False
        p["score"] = 0

    # set initial target for the room
    rooms[room_id]["target"] = pick_random_target()

    # broadcast new character (don't reveal name)
    emit("new_character", {"message": "Game started"}, room=room_id)

    # if timed mode, start timer in background
    if rooms[room_id]["mode"] == "timed":
        socketio.start_background_task(timed_round, room_id)

def timed_round(room_id):
    timer = rooms[room_id]["timer"]
    for t in range(timer, 0, -1):
        socketio.emit("timer_tick", {"time": t}, room=room_id)
        socketio.sleep(1)
    leaderboard = {p: rooms[room_id]["players"][p].get("score", 0) for p in rooms[room_id]["players"]}
    socketio.emit("game_over", {"leaderboard": leaderboard}, room=room_id)
    rooms[room_id]["started"] = False
    rooms[room_id]["target"] = pick_random_target()

# ---------------------- New: multiplayer character guessing (socket) ----------------------
@socketio.on("make_guess")
def handle_make_guess(data):
    """
    New socket event to submit a character name guess during a multiplayer round.
    data: { room_id, player, guess }
    Modes:
      - 'first_to_guess' -> first correct guess ends the round and emits game_over with winner
      - 'timed' -> each correct guess awards 1 point, then a new target is picked and round continues until timer end
    """
    room_id = data.get("room_id")
    player = data.get("player")
    guess = (data.get("guess") or "").strip()

    if not room_id or not player or not guess:
        emit("error", {"msg": "room_id, player and guess required"})
        return

    if room_id not in rooms:
        emit("error", {"msg": "Room not found"})
        return

    if player not in rooms[room_id]["players"]:
        emit("error", {"msg": "Player not in room"})
        return

    if not rooms[room_id].get("started"):
        emit("error", {"msg": "Round not started"})
        return

    # current room target
    target_char = rooms[room_id].get("target")
    if not target_char:
        emit("error", {"msg": "No target set for room"})
        return

    # compare guessed name to target
    if guess.lower() == target_char.name.lower():
        # correct guess
        # first_to_guess: end immediately and announce winner
        if rooms[room_id]["mode"] == "first_to_guess":
            # award 1 point to winner for record (optional)
            rooms[room_id]["players"][player]["score"] = rooms[room_id]["players"][player].get("score", 0) + 1
            leaderboard = {p: rooms[room_id]["players"][p].get("score", 0) for p in rooms[room_id]["players"]}
            emit("game_over", {"winner": player, "character": {
                "name": target_char.name,
                "gender": target_char.gender,
                "first_arc": target_char.first_arc,
                "affiliation": target_char.affiliation,
                "bounty": str(target_char.bounty),
                "height": str(target_char.height),
                "devil_fruit_type": target_char.devil_fruit_type,
                "haki": "; ".join(target_char.haki) if target_char.haki else "None"
            }, "leaderboard": leaderboard}, room=room_id)
            rooms[room_id]["started"] = False
            # prepare next target for future rounds
            rooms[room_id]["target"] = pick_random_target()
        else:
            # timed mode: award a point, broadcast score update, and immediately pick a new target
            rooms[room_id]["players"][player]["score"] = rooms[room_id]["players"][player].get("score", 0) + 1
            points = rooms[room_id]["players"][player]["score"]
            leaderboard = {p: rooms[room_id]["players"][p].get("score", 0) for p in rooms[room_id]["players"]}
            emit("correct_guess", {"player": player, "new_score": points}, room=room_id)
            emit("score_update", {"leaderboard": leaderboard}, room=room_id)
            # pick new char for room and notify clients
            rooms[room_id]["target"] = pick_random_target()
            emit("new_character", {"message": "New character selected after correct guess"}, room=room_id)
    else:
        # incorrect guess: broadcast optional feedback (do not reveal target)
        emit("incorrect_guess", {"player": player, "guess": guess}, room=room_id)

# ---------------------- Existing attribute-guessing (keep as-is) ----------------------
@socketio.on("guess_attribute")
def handle_guess_attribute(data):
    room_id = data.get("room_id")
    player = data.get("player")
    attribute = data.get("attribute")
    value = data.get("value")
    if room_id not in rooms or player not in rooms[room_id]["players"]:
        emit("error", {"msg": "Invalid room or player"})
        return

    target = rooms[room_id]["target"]
    player_state = rooms[room_id]["players"][player]
    attribute = attribute.strip().lower()
    if attribute not in ATTRIBUTES:
        emit("guess_result", {"ok": False, "msg": "Unknown attribute", "attribute": attribute}, room=room_id)
        return

    if attribute in player_state["guessed"]:
        emit("guess_result", {"ok": False, "msg": "Already guessed", "attribute": attribute}, room=room_id)
        return

    correct = False
    if attribute == "bounty":
        digits = re.sub(r"[^\d]", "", value)
        try:
            guess_val = int(digits)
            correct = (guess_val == target.bounty)
        except:
            correct = False
    elif attribute == "height":
        try:
            guess_val = float(value)
            correct = (abs(guess_val - target.height) < 0.01)
        except:
            correct = False
    elif attribute == "haki":
        guess_tokens = {t.strip().lower() for t in value.split(";") if t.strip()}
        target_tokens = {t.strip().lower() for t in target.haki}
        correct = bool(guess_tokens & target_tokens)
    else:
        correct = (value.strip().lower() == getattr(target, attribute).strip().lower())

    points_awarded = 0
    if correct:
        player_state["guessed"].add(attribute)
        player_state["score"] = player_state.get("score", 0) + 5
        points_awarded += 5
        if not player_state.get("bonus_given", False):
            if all(attr in player_state["guessed"] for attr in ATTRIBUTES):
                player_state["score"] += 20
                player_state["bonus_given"] = True
                points_awarded += 20

    emit("guess_result", {
        "player": player, "attribute": attribute,
        "correct": correct, "points_awarded": points_awarded,
        "current_score": player_state.get("score", 0)
    }, room=room_id)

    leaderboard = {p: rooms[room_id]["players"][p].get("score", 0) for p in rooms[room_id]["players"]}
    emit("score_update", {"leaderboard": leaderboard}, room=room_id)

    if rooms[room_id]["mode"] == "first_to_complete" and player_state.get("bonus_given", False):
        emit("game_over", {"leaderboard": leaderboard, "winner": player}, room=room_id)
        rooms[room_id]["started"] = False
        rooms[room_id]["target"] = pick_random_target()

@socketio.on("skip_character")
def handle_skip_character(data):
    room_id = data.get("room_id")
    if room_id not in rooms:
        emit("error", {"msg": "Room not found"})
        return
    rooms[room_id]["target"] = pick_random_target()
    for p in rooms[room_id]["players"].values():
        p["guessed"] = set()
        p["bonus_given"] = False
    emit("new_character", {"message": "Character skipped"}, room=room_id)

# ---------------------- HTTP endpoints ----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/reset", methods=["POST"])
def reset():
    global target
    room_id = request.form.get("room_id")
    if room_id and room_id in rooms:
        rooms[room_id]["target"] = pick_random_target()
        for p in rooms[room_id]["players"].values():
            p["guessed"] = set()
            p["bonus_given"] = False
            p["score"] = 0
        return jsonify({"message": "Room new round started", "room_id": room_id})
    target = pick_random_target()
    return jsonify({"message": "New round started"})

@app.route("/guess", methods=["POST"])
def guess():

    
    # single-player or pre-start room guesses
    guess_name = request.form.get("guess", "").strip()
    room_id = request.form.get("room_id")
    if not guess_name:
        return jsonify({"error": "No guess provided"})
    if room_id:
        # room-level guess (allowed only if room exists and not started)
        if room_id not in rooms:
            return jsonify({"error": "Room not found"})
        
        use_target = rooms[room_id]["target"]
    else:
        use_target = target

    matches = [c for c in characters if c.name.lower() == guess_name.lower()]
    if not matches:
        return jsonify({"error": "Character not found"})
    guess_char = matches[0]
    feedback = compare_characters(use_target, guess_char)
    result = {
        "name": {"value": guess_char.name, "status": "none"},
        "gender": {"value": guess_char.gender, "status": feedback["gender"]["status"]},
        "first_arc": {"value": guess_char.first_arc, "status": feedback["first_arc"]["status"]},
        "affiliation": {"value": guess_char.affiliation, "status": feedback["affiliation"]["status"]},
        "bounty": {"value": str(guess_char.bounty), "status": feedback["bounty"]["status"]},
        "height": {"value": str(guess_char.height), "status": feedback["height"]["status"]},
        "devil_fruit_type": {"value": guess_char.devil_fruit_type, "status": feedback["devilfruit"]["status"]},
        "haki": {"value": "; ".join(guess_char.haki) if guess_char.haki else "None", "status": feedback["haki"]["status"]},
    }
    if guess_char.name == use_target.name:
        for k in result:
            result[k]["status"] = "correct"
        result["winner"] = True
    return jsonify(result)

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        results = typesense_client.collections["characters"].documents.search({
            "q": q,
            "query_by": "name",
            "prefix": True,
            "limit": 20
        })
        names = list({hit["document"]["name"] for hit in results["hits"]})
        return jsonify([{"name": name} for name in names])
    except Exception as e:
        print("Search error:", e)
        return jsonify([])

@app.route("/reveal", methods=["GET"])
def reveal():
    room_id = request.args.get("room_id")
    if room_id and room_id in rooms:
        t = rooms[room_id]["target"]
    else:
        t = target
    if not t:
        return jsonify({"error":"No active target"})
    return jsonify({
        "name": t.name,
        "gender": t.gender,
        "first_arc": t.first_arc,
        "affiliation": t.affiliation,
        "bounty": str(t.bounty),
        "height": str(t.height),
        "devil_fruit_type": t.devil_fruit_type,
        "haki": "; ".join(t.haki) if t.haki else "None"
    })

# ---------------------- run ----------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
