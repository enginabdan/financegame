const API_BASE = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";

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
    { label: "Tax Reserve", value: money(state.tax_reserve), className: "day" },
    { label: "Debt", value: money(state.debt), className: "stress" },
    { label: "Stress", value: state.stress, className: "stress" },
    { label: "Status", value: state.status, className: "status" },
  ];

  if (typeof score === "number") {
    cells.push({ label: "Score", value: `${score}/100`, className: "day" });
  }
  if (state.class_code) {
    cells.push({ label: "Class", value: state.class_code, className: "status" });
  }
  if (state.assignment_code) {
    cells.push({ label: "Assignment", value: state.assignment_code, className: "day" });
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
  const classCode = (document.getElementById("classCode").value || "").trim().toUpperCase();
  const assignmentCode = (document.getElementById("assignmentCode").value || "").trim().toUpperCase();

  const useAssignmentJoin = classCode.length > 0 || assignmentCode.length > 0;
  if (useAssignmentJoin && (!classCode || !assignmentCode)) {
    alert("Enter both Class Code and Assignment Code, or leave both empty.");
    return;
  }

  const endpoint = useAssignmentJoin ? "/api/student/join-assignment" : "/api/new-game";
  const payload = useAssignmentJoin
    ? { player_name: playerName, class_code: classCode, assignment_code: assignmentCode }
    : { player_name: playerName, city };
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    alert(body.detail || "Failed to start game");
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
