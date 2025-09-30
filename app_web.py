from flask import Flask, render_template, request, jsonify
import csv, random
import typesense

# Load arcs order
with open("Arcs.txt", encoding="utf-8") as f:
    arcs_order = [line.strip() for line in f if line.strip()]

app = Flask(__name__)

# --- Typesense client ---
typesense_client = typesense.Client({
    "nodes": [{
        "host": "apn0q798izyjv4u3p-1.a1.typesense.net",
        "port": "443",
        "protocol": "https"
    }],
    "api_key": "59gbcoo05qOMzKKqQWOGXVJRu6CRmrLt",  # Use your actual key here
    "connection_timeout_seconds": 2
})

# --- Character class ---
class Character:
    def __init__(self, name, first_arc, affiliation, bounty, height, devil_fruit_type, haki, gender):
        self.name = name
        self.first_arc = first_arc
        self.affiliation = affiliation
        self.bounty = int(bounty)
        self.height = float(height)
        self.devil_fruit_type = devil_fruit_type
        self.haki = set(h.strip() for h in haki.split(";") if h.strip() and h.strip().lower() != "none")
        self.gender = gender

# --- Load characters ---
def load_characters(filename="Characters.txt"):
    characters = []
    with open(filename, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            characters.append(Character(
                row["name"], row["first_arc"], row["affiliation"], row["bounty"],
                row["height"], row["devil_fruit_type"], row["haki"], row["gender"]
            ))
    return characters

characters = load_characters()
target = random.choice(characters)

# --- Typesense collection schema ---
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

# --- Ensure collection exists ---
try:
    typesense_client.collections.create(character_schema)
    print("✅ Collection created")
except Exception as e:
    print("⚠️ Collection exists or failed:", e)

# --- Upsert characters ---
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

# --- Compare characters ---
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

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/reset", methods=["POST"])
def reset():
    global target
    target = random.choice(characters)
    return jsonify({"message": "New round started"})

@app.route("/guess", methods=["POST"])
def guess():
    guess_name = request.form.get("guess", "").strip()
    matches = [c for c in characters if c.name.lower() == guess_name.lower()]
    if not matches:
        return jsonify({"error": "Character not found"})
    guess_char = matches[0]
    feedback = compare_characters(target, guess_char)
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
    if guess_char.name == target.name:
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
            "prefix": True,   # <-- allows 'starts with' matches
            "limit": 20       # limit results to avoid huge dropdowns
        })
        # Remove duplicates
        names = list({hit["document"]["name"] for hit in results["hits"]})
        return jsonify([{"name": name} for name in names])
    except Exception as e:
        print("Search error:", e)
        return jsonify([])

@app.route("/reveal", methods=["GET"])
def reveal():
    if not target:
        return jsonify({"error": "No active game"})
    revealed = {
        "name": target.name,
        "gender": target.gender,
        "first_arc": target.first_arc,
        "affiliation": target.affiliation,
        "bounty": str(target.bounty),
        "height": str(target.height),
        "devil_fruit_type": target.devil_fruit_type,
        "haki": "; ".join(target.haki) if target.haki else "None",
    }
    return jsonify(revealed)

if __name__ == "__main__":
    app.run(debug=True)
