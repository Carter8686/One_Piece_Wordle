const form = document.getElementById("guess-form");

function formatBounty(bounty) {
    return `
        <img src="/static/Berrysymbol.svg" alt="Berry" class="berry-icon">
        ${Number(bounty).toLocaleString()}
    `;
}

const guessContainer = document.getElementById("guess-container");

// --- Handle guesses ---
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

    // --- Create a new row for this guess ---
    const row = document.createElement("div");
    row.classList.add("guess-row");

    const attributes = ["name", "gender", "first_arc", "affiliation", "bounty", "height", "devil_fruit_type", "haki"];

    attributes.forEach(attr => {
        const box = document.createElement("div");
        box.classList.add("attribute-box");

        if (attr !== "name") {
            box.classList.add(data[attr].status); // correct/incorrect/partial/higher/lower/earlier/later
        }

        if (attr === "bounty") {
            box.innerHTML = formatBounty(data[attr].value);
        } else {
            box.innerHTML = `<span>${data[attr].value}</span>`;
        }

        row.appendChild(box);
    });

    // Add the completed row at the top
    guessContainer.prepend(row);

    // Clear input
    document.getElementById("guess").value = "";
});

// --- New Round button ---
const newRoundBtn = document.getElementById("newRoundBtn");
if (newRoundBtn) {
    newRoundBtn.addEventListener("click", async () => {
        await fetch("/reset", { method: "POST" });
        guessContainer.innerHTML = "";
        document.getElementById("result").innerText = "";
        document.getElementById("guess").value = "";
    });
}

// --- Typesense Search Suggestions ---
const input = document.getElementById("guess");
const suggestions = document.getElementById("suggestions");

input.addEventListener("input", async () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
        suggestions.innerHTML = "";
        return;
    }

    const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();

    const uniqueNames = [...new Set(data.map(hit => hit.name))];

    suggestions.innerHTML = "";
    uniqueNames.forEach(name => {
        const option = document.createElement("div");
        option.classList.add("suggestion");

        // Highlight only the first letters that match the typed prefix
        const prefix = name.substring(0, q.length);
        const rest = name.substring(q.length);
        const highlightedName = `<span class="match">${prefix}</span>${rest}`;

        option.innerHTML = highlightedName;

        option.onclick = () => {
            input.value = name;
            suggestions.innerHTML = "";
        };

        suggestions.appendChild(option);
    });
});

// --- Reveal button ---
const revealBtn = document.getElementById("revealBtn");
if (revealBtn) {
    revealBtn.addEventListener("click", async () => {
        const res = await fetch("/reveal");
        const data = await res.json();

        if (data.error) {
            document.getElementById("result").innerText = data.error;
            return;
        }

        const revealDiv = document.createElement("div");
        revealDiv.classList.add("reveal-box");
        revealDiv.innerHTML = `
            <h3>Revealed Character</h3>
            <p><strong>Name:</strong> ${data.name}</p>
            <p><strong>Gender:</strong> ${data.gender}</p>
            <p><strong>First Arc:</strong> ${data.first_arc}</p>
            <p><strong>Affiliation:</strong> ${data.affiliation}</p>
            <p><strong>Bounty:</strong> ${data.bounty}</p>
            <p><strong>Height:</strong> ${data.height}</p>
            <p><strong>Devil Fruit:</strong> ${data.devil_fruit_type}</p>
            <p><strong>Haki:</strong> ${data.haki}</p>
        `;

        const resultBox = document.getElementById("result");
        resultBox.innerHTML = "";
        resultBox.appendChild(revealDiv);
    });
}

// Close suggestions when clicking outside
document.addEventListener("click", (e) => {
    if (!input.contains(e.target) && !suggestions.contains(e.target)) {
        suggestions.innerHTML = "";
    }
});
