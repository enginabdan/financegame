const API_BASE = "http://127.0.0.1:8000";

let sessionId = null;

const startBtn = document.getElementById("startBtn");
const advanceBtn = document.getElementById("advanceBtn");
const stats = document.getElementById("stats");
const log = document.getElementById("log");

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function renderState(state, score = null) {
  stats.innerHTML = "";

  const cells = [
    { label: "Day", value: `${state.day}/30`, className: "day" },
    { label: "Cash", value: money(state.cash), className: "cash" },
    { label: "Stress", value: state.stress, className: "stress" },
    { label: "Status", value: state.status, className: "status" },
  ];

  if (typeof score === "number") {
    cells.push({ label: "Score", value: `${score}/100`, className: "day" });
  }

  for (const cell of cells) {
    const div = document.createElement("div");
    div.className = `stat ${cell.className}`;
    div.innerHTML = `<div>${cell.label}</div><div>${cell.value}</div>`;
    stats.appendChild(div);
  }
}

function addLog(result, score) {
  const item = document.createElement("article");
  item.className = "log-item";
  item.innerHTML = `
    <strong>Day ${result.day} - ${result.event_title}</strong>
    <p>${result.event_text}</p>
    <p class="meta">Gross: ${money(result.gross_income)} | Fees: ${money(result.platform_fees)} | Variable: ${money(result.variable_costs)}</p>
    <p class="meta">Household: ${money(result.household_costs)} | Tax reserve: ${money(result.tax_reserve)} | Event: ${money(result.event_cash_impact)}</p>
    <p class="meta">End cash: ${money(result.end_cash)} | Score: ${score}/100</p>
  `;
  log.prepend(item);
}

async function startGame() {
  const playerName = document.getElementById("playerName").value || "Student";
  const city = document.getElementById("city").value || "Charlotte, NC";

  const response = await fetch(`${API_BASE}/api/new-game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: playerName, city }),
  });

  if (!response.ok) {
    alert("Failed to start game");
    return;
  }

  const state = await response.json();
  sessionId = state.session_id;
  log.innerHTML = "";
  renderState(state);
}

async function advanceDay() {
  if (!sessionId) {
    alert("Start a game first.");
    return;
  }

  const allocation = {
    gig_hours: Number(document.getElementById("gigHours").value || 0),
    delivery_hours: Number(document.getElementById("deliveryHours").value || 0),
    marketplace_hours: Number(document.getElementById("marketHours").value || 0),
  };

  const totalHours = allocation.gig_hours + allocation.delivery_hours + allocation.marketplace_hours;
  if (totalHours > 14) {
    alert("Total daily hours cannot exceed 14.");
    return;
  }

  const response = await fetch(`${API_BASE}/api/advance-day`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, allocation }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    alert(body.detail || "Failed to advance day");
    return;
  }

  const data = await response.json();
  renderState(data.state, data.score);
  addLog(data.result, data.score);
}

startBtn.addEventListener("click", () => {
  startGame().catch((err) => {
    console.error(err);
    alert("Unexpected error while starting game");
  });
});

advanceBtn.addEventListener("click", () => {
  advanceDay().catch((err) => {
    console.error(err);
    alert("Unexpected error while advancing day");
  });
});
