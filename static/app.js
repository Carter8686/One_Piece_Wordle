// static/app.js

// ---------------- Helpers ----------------
function escapeHtml(unsafe) {
  return unsafe
       .replace(/&/g, "&amp;")
       .replace(/</g, "&lt;")
       .replace(/>/g, "&gt;")
       .replace(/"/g, "&quot;")
       .replace(/'/g, "&#039;");
}

const form = document.getElementById("guess-form");
const guessContainer = document.getElementById("guess-container");
const input = document.getElementById("guess");
const suggestions = document.getElementById("suggestions");
const roomIdInput = document.getElementById("roomIdInput");
const resultDiv = document.getElementById("result");
const playersList = document.getElementById("playersList");
const roomInfo = document.getElementById("roomInfo");
const leaderboardEl = document.getElementById("leaderboard");
const timerEl = document.getElementById("timer");

input.setAttribute("autocomplete", "off");

// ---------------- UI rendering ----------------
function formatBounty(bounty) {
    return `
        <img src="/static/berrysymbol.svg" alt="Berry" class="berry-icon">
        ${Number(bounty).toLocaleString()}
    `;
}

function renderGuessRow(data) {
    const row = document.createElement("div");
    row.classList.add("guess-row");

    const attributes = ["name", "gender", "first_arc", "affiliation", "bounty", "height", "devil_fruit_type", "haki"];

    attributes.forEach(attr => {
        const box = document.createElement("div");
        box.classList.add("attribute-box");

        if (attr !== "name") {
            const status = (data[attr] && data[attr].status) ? data[attr].status : "neutral";
            box.classList.add(status);
        }

        if (attr === "bounty") {
            box.innerHTML = data[attr] && data[attr].value ? formatBounty(data[attr].value) : "<span>—</span>";
        } else {
            box.innerHTML = `<span>${data[attr] && data[attr].value ? escapeHtml(String(data[attr].value)) : "—"}</span>`;
        }
        row.appendChild(box);
    });

    guessContainer.prepend(row);
}

// ---------------- Single-player / Room guess (form submit) ----------------
form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const guessName = input.value.trim();
    if (!guessName) return;

    const roomId = roomIdInput.value || "";
    const body = new URLSearchParams({ guess: guessName });
    if (roomId) body.append("room_id", roomId);

    const res = await fetch("/guess", {
        method: "POST",
        body: body
    });

    const data = await res.json();

    if (data.error) {
        resultDiv.innerText = data.error;
        return;
    }

    if (data.winner) {
        resultDiv.innerText = `🎉 Correct! The character was ${data.name.value}`;
        socket.emit("character_guessed", { room_id: roomId, player: playerName, character: data.name.value });
    } else {
        resultDiv.innerText = "";
    }

    renderGuessRow(data);

    input.value = "";
    suggestions.innerHTML = "";
});

// ---------------- New round / Reveal ----------------
document.getElementById("newRoundBtn").addEventListener("click", async () => {
    const roomId = roomIdInput.value || "";
    const body = new URLSearchParams();
    if (roomId) body.append("room_id", roomId);
    await fetch("/reset", { method: "POST", body: body });
    guessContainer.innerHTML = "";
    resultDiv.innerText = "";
});

document.getElementById("revealBtn").addEventListener("click", async () => {
    const roomId = roomIdInput.value || "";
    const url = roomId ? `/reveal?room_id=${encodeURIComponent(roomId)}` : `/reveal`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) {
        resultDiv.innerText = data.error;
        return;
    }
    const revealDiv = document.createElement("div");
    revealDiv.classList.add("reveal-box");
    revealDiv.innerHTML = `
        <h3>Revealed Character</h3>
        <p><strong>Name:</strong> ${escapeHtml(data.name)}</p>
        <p><strong>Gender:</strong> ${escapeHtml(data.gender)}</p>
        <p><strong>First Arc:</strong> ${escapeHtml(data.first_arc)}</p>
        <p><strong>Affiliation:</strong> ${escapeHtml(data.affiliation)}</p>
        <p><strong>Bounty:</strong> ${escapeHtml(data.bounty)}</p>
        <p><strong>Height:</strong> ${escapeHtml(data.height)}</p>
        <p><strong>Devil Fruit:</strong> ${escapeHtml(data.devil_fruit_type)}</p>
        <p><strong>Haki:</strong> ${escapeHtml(data.haki)}</p>
    `;
    resultDiv.innerHTML = "";
    resultDiv.appendChild(revealDiv);
});

// ---------------- Typesense Autocomplete ----------------
input.addEventListener("input", async () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
        suggestions.innerHTML = "";
        return;
    }
    try {
        const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        const uniqueNames = [...new Set(data.map(hit => hit.name))];
        suggestions.innerHTML = "";
        uniqueNames.forEach(name => {
            const option = document.createElement("div");
            option.classList.add("suggestion");
            const prefix = name.substring(0, q.length);
            const rest = name.substring(q.length);
            option.innerHTML = `<span class="match">${escapeHtml(prefix)}</span>${escapeHtml(rest)}`;
            option.addEventListener("click", () => {
                input.value = name;
                suggestions.innerHTML = "";
            });
            suggestions.appendChild(option);
        });
    } catch (err) {
        console.error("search error", err);
        suggestions.innerHTML = "";
    }
});

document.addEventListener("click", (e) => {
    if (!input.contains(e.target) && !suggestions.contains(e.target)) {
        suggestions.innerHTML = "";
    }
});

// ---------------- Socket.IO Multiplayer ----------------
const socket = io();
let currentRoom = null;
let playerName = null;
const createBtn = document.getElementById("createRoomBtn");
const joinBtn = document.getElementById("joinRoomBtn");
const startBtn = document.getElementById("startGameBtn");
const setModeBtn = document.getElementById("setModeBtn");
const skipBtn = document.getElementById("skipBtn");

createBtn.addEventListener("click", () => {
    const name = prompt("Enter your display name:");
    if (!name) return alert("Name required");
    playerName = name;
    const mode = prompt("Mode: 'timed' or 'first_to_complete' (default timed):", "timed") || "timed";
    const timer = mode === "timed" ? parseInt(prompt("Round length in seconds (default 120):", "120")) || 120 : 0;
    socket.emit("create_room", { player: playerName, mode, timer });
});

joinBtn.addEventListener("click", () => {
    const name = prompt("Enter your display name:");
    if (!name) return alert("Name required");
    const room = prompt("Enter room ID to join:");
    if (!room) return alert("Room ID required");
    playerName = name;
    socket.emit("join_room", { room_id: room.trim(), player: playerName });
});

startBtn.addEventListener("click", () => {
    if (!currentRoom || !playerName) return alert("Join a room first");
    socket.emit("start_game", { room_id: currentRoom, player: playerName });
});

setModeBtn.addEventListener("click", () => {
    if (!currentRoom) return alert("Join a room first");
    const mode = prompt("Set mode: 'timed' or 'first_to_complete' (owner only):", "timed") || "timed";
    const timer = mode === "timed" ? (parseInt(prompt("Round length in seconds (default 120):", "120")) || 120) : 0;
    socket.emit("set_mode", { room_id: currentRoom, mode, timer });
});

skipBtn.addEventListener("click", () => {
    if (!currentRoom) return alert("Join a room first");
    socket.emit("skip_character", { room_id: currentRoom });
});

// ---------------- Socket Event Handlers ----------------
socket.on("room_joined", (data) => {
    currentRoom = data.room_id;
    roomIdInput.value = currentRoom;
    roomInfo.innerText = `Room: ${currentRoom} (owner: ${data.owner})`;
    playersList.innerHTML = `Players: ${data.players.join(", ")}`;
});

socket.on("player_joined", (data) => {
    playersList.innerText = `Players: ${data.players.join(", ")}`;
});

socket.on("mode_set", (data) => {
    alert(`Mode set: ${data.mode} (timer ${data.timer}s)`);
});

socket.on("new_character", (data) => {
    alert(data.message || "New character!");
    guessContainer.innerHTML = "";
});

socket.on("timer_tick", (data) => {
    timerEl.innerText = `Time: ${data.time}s`;
});

socket.on("guess_result", (data) => {
    const msg = `${data.player} guessed ${data.attribute} — ${data.correct ? "✅ correct" : "❌ wrong"} (+${data.points_awarded}) — score ${data.current_score}`;
    console.log(msg);
    const d = document.createElement("div");
    d.innerText = msg;
    d.style.padding = "6px";
    d.style.borderTop = "1px solid #ccc";
    resultDiv.prepend(d);
});

socket.on("score_update", (data) => {
    leaderboardEl.innerHTML = Object.entries(data.leaderboard).map(([p,s]) => `<div>${escapeHtml(p)}: ${s}</div>`).join("");
});

socket.on("game_over", (data) => {
    alert("🏆 Game over! Check leaderboard.");
    console.log("game_over", data);
});

socket.on("error", (data) => {
    alert("Server error: " + (data.msg || JSON.stringify(data)));
});

// helper: manual attribute guess (debug)
window.submitAttributeGuess = function () {
    if (!currentRoom || !playerName) return alert("Join a room first");
    const attribute = prompt("Attribute to guess (gender, first_arc, affiliation, bounty, height, devil_fruit_type, haki):");
    if (!attribute) return;
    const value = prompt(`Value for "${attribute}":`);
    if (value === null) return;
    socket.emit("guess_attribute", { room_id: currentRoom, player: playerName, attribute, value });
};
