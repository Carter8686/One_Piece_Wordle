import csv
import random

class Character:
    def __init__(self, name, gender, first_arc, affiliation, bounty, height, devil_fruit_type, haki):
        self.name = name
        self.first_arc = first_arc
        self.gender = gender
        self.affiliation = affiliation
        self.bounty = int(bounty)
        self.height = float(height)
        self.devil_fruit_type = devil_fruit_type
        self.haki = set([h.strip() for h in haki.split(";")if h.strip()])
       

def load_characters(filename):
    characters = []
    with open(filename, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = Character(
                row["name"],
                row["gender"],
                row["first_arc"],
                row["affiliation"],
                row["bounty"],
                row["height"],
                row["devil_fruit_type"],
                row["haki"]
            )
            characters.append(c)
    return characters
    
def compare_characters(target, guess):

     #Gender
     print("Gender: ", "Correct---" + guess.gender if target.gender == guess.gender else "Wrong---" + guess.gender)

     # first arc
     print("First Arc:", "Correct---" + guess.first_arc if target.first_arc == guess.first_arc else "Wrong---" + guess.first_arc)

     # Affiliation
     print("Affiliation:", "Correct---" + guess.affiliation if target.affiliation == guess.affiliation else "Wrong---" + guess.affiliation)
     
     # Bounty
     if target.bounty == guess.bounty:
         print("Bounty: Correct---" + str(guess.bounty))
     elif target.bounty > guess.bounty:
         print("Bounty: Higher---" + str(guess.bounty))
     else:
         print("Bounty: Lower---" + str(guess.bounty))
    
     # Height
     if target.height == guess.height:
         print("Height: Correct---" + str(guess.height))
     elif target.height > guess.height:
         print("Height: Higher---" + str(guess.height))
     else:
         print("Height: Lower---" + str(guess.height))
    
     # Devil Fruit Type
     print("Devil Fruit Type:", "Correct---" + target.devil_fruit_type if target.devil_fruit_type == guess.devil_fruit_type else "Wrong---" + guess.devil_fruit_type)
    
     # Haki
     if target.haki == guess.haki:
         print("Haki: Correct---" + ", ".join(guess.haki))
     elif guess.haki & target.haki:
         print("Haki: Partial---" + ", ".join(guess.haki))
     else:
         print("Haki: Wrong---" + ", ".join(guess.haki))

def main():
    characters = load_characters("Characters.txt")
    if not characters:
        print("No characters loaded.")
        return
    target = random.choice(characters)
    print("Welcome to One Piece Character Guessing Game!")
    print("Enter 'quit' to exit")


    while True:
        guess_name = input("\nEnter your guess: ").strip()
        if guess_name.lower() == 'quit':
            print("Thanks for playing!")
            break

        matches = [c for c in characters if c.name == guess_name]
        if not matches:
            print("Character not found. Try again.")
            continue
        guess = matches[0]
        if guess.name == target.name:
            print(f"Correct! The character was {target.name}!")
            break
        else:
            compare_characters(target, guess)

if __name__ == "__main__":
    main() 