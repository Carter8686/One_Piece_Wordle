from flask import Flask, render_template, request, jsonify
import csv
import random

with open("Arcs.txt", encoding="utf-8") as f:
    arcs_order = [line.strip() for line in f if line.strip()]

app = Flask(__name__)

class Character:
    def __init__(self, name, first_arc, affiliation, bounty, height, devil_fruit_type, haki, gender):
        self.name = name
        self.first_arc = first_arc
        self.affiliation = affiliation
        self.bounty = int(bounty)
        self.height = float(height)
        self.devil_fruit_type = devil_fruit_type
        self.haki = set([h.strip() for h in haki.split(";") if h.strip() and h.strip().lower() != "none"])
        self.gender = gender

def load_characters(filename="Characters.txt"):
    characters = []
    with open(filename, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = Character(
                row["name"],
                row["first_arc"],
                row["affiliation"],
                row["bounty"],
                row["height"],
                row["devil_fruit_type"],
                row["haki"],
                row["gender"]
            )
            characters.append(c)
    return characters

characters = load_characters()
target = random.choice(characters)

def compare_characters(target, guess):
    feedback = {}
    feedback["name"] = {"value": guess.name, "status": "neutral"}  # name is not colored
    feedback["gender"] = {"value": guess.gender, "status": "correct" if target.gender == guess.gender else "incorrect"}
    # First Arc comparison
    if target.first_arc == guess.first_arc:
        status = "correct"
    else:
        try:
            target_idx = arcs_order.index(target.first_arc)
            guess_idx = arcs_order.index(guess.first_arc)
            if target_idx < guess_idx:
                status = "later"   # means target appears later in story
            else:
                status = "earlier" # means target appears earlier
        except ValueError:
            status = "incorrect"  # fallback if arc not found
    feedback["first_arc"] = {"value": guess.first_arc, "status": status}
    
    # Affiliation
    feedback["affiliation"] = {"value": guess.affiliation, "status": "correct" if target.affiliation == guess.affiliation else "incorrect"}

    # Bounty
    if target.bounty == guess.bounty:
        status = "correct"
    elif target.bounty > guess.bounty:
        status = "higher"
    else:
        status = "lower"
    feedback["bounty"] = {"value": guess.bounty, "status": status}

    # Height
    if target.height == guess.height:
        status = "correct"
    elif target.height > guess.height:
        status = "higher"
    else:
        status = "lower"
    feedback["height"] = {"value": guess.height, "status": status}

    # Devil Fruit
    status = "correct" if target.devil_fruit_type == guess.devil_fruit_type else "incorrect"
    feedback["devilfruit"] = {"value": guess.devil_fruit_type, "status": status}

    # Haki
    if target.haki == guess.haki:
        status = "correct"
    elif guess.haki & target.haki:
        status = "partial"
    else:
        status = "incorrect"
    feedback["haki"] = {"value": ", ".join(guess.haki) if guess.haki else "None", "status": status}

    return feedback

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

    # Build result in consistent format
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

    # If winner, mark all as correct + set winner flag
    if guess_char.name == target.name:
        for k in result:
            result[k]["status"] = "correct"
        result["winner"] = True

    return jsonify(result)



if __name__ == "__main__":
    app.run(debug=True)
