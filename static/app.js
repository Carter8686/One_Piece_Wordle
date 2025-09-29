const form = document.getElementById("guess-form");
const guessContainer = document.getElementById("guess-container");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const guessName = document.getElementById("guess").value.trim();
    if (!guessName) return;

    const res = await fetch("/guess", {
        method: "POST",
        body: new URLSearchParams({ guess: guessName })
    });

    const data = await res.json();

    if (data.error) {
        document.getElementById("result").innerText = data.error;
        return;
    }

    if (data.winner) {
        document.getElementById("result").innerText = `Correct! The character was ${data.name.value}`;
    }

    // Create a new row for this guess
    const row = document.createElement("div");
    row.classList.add("guess-row");

    // Left-to-right order of attributes
    const attributes = ["name", "gender", "first_arc", "affiliation", "bounty", "height", "devil_fruit_type", "haki"];

attributes.forEach(attr => {
    const box = document.createElement("div");
    box.classList.add("attribute-box");

    if (attr !== "name") {
        box.classList.add(data[attr].status); // apply correct/incorrect/partial
    }

    box.innerHTML = `<span>${data[attr].value}</span>`; // show the actual guessed attribute
    row.appendChild(box);
});


    // Add this guess at the top of the container
    guessContainer.prepend(row);

    // Clear the input box
    document.getElementById("guess").value = "";
});

// --- New Round button ---
const newRoundBtn = document.getElementById("newRoundBtn");

if (newRoundBtn) {
    newRoundBtn.addEventListener("click", async () => {
        await fetch("/reset", { method: "POST" });

        // Clear UI
        guessContainer.innerHTML = "";
        document.getElementById("result").innerText = "";
        document.getElementById("guess").value = "";
    });
}


