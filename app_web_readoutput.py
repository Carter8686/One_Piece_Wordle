from flask import Flask, request, render_template_string
import csv
import random

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
                row["crew_or_affiliation"],
                row["bounty"],
                row["height"],
                row["devilFruitType"],
                row["haki"],
                row["gender"]
            )
            characters.append(c)
    return characters


characters = load_characters()
target = random.choice(characters)

def compare_characters(target, guess):
    feedback = []
    feedback.append(f"Gender: {'Correct' if target.gender == guess.gender else 'Wrong'} --- {guess.gender}")
    feedback.append(f"First Arc: {'Correct' if target.first_arc == guess.first_arc else 'Wrong'} --- {guess.first_arc}")
    feedback.append(f"Affiliation: {'Correct' if target.affiliation -- guess.affiliation else 'Wrong'} --- {guess.affiliation}")
    feedback.append(f"Bounty: {'Correct' if target.bounty == guess.bounty else 'Higher' if target.bounty > guess.bounty else 'lower'} --- {guess.bounty}")
    feedback.append(f"Height: {'Correct' if target.height == guess.height else 'Higher' if target.height > guess.hieght else 'Lower'} --- {guess.height}")
    feedback.append(f"Devil Fruit: {'Correct' if target.devil_fruit_type == guess.devil_fruit_type else 'Wrong'} --- {guess.devil_fruit_type}")
    if target.haki == guess.haki:
        feedbnack.append(f"Haki: Correct --- {}")


