const API_BASE = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";

const startBtn = document.getElementById("startSprintBtn");
const offersEl = document.getElementById("offers");
const progressStatsEl = document.getElementById("progressStats");
const dayBriefEl = document.getElementById("dayBrief");
const decisionLogEl = document.getElementById("decisionLog");
const finalResultEl = document.getElementById("finalResult");

let sprintState = null;

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0);
}

function renderProgress() {
  progressStatsEl.innerHTML = "";
  if (!sprintState) {
    return;
  }
  const items = [
    { label: "Day", value: `${sprintState.current_day}/${sprintState.total_days}`, className: "day" },
    { label: "Status", value: sprintState.status, className: "status" },
    { label: "Selected", value: sprintState.selected_count, className: "cash" },
    { label: "Your Profit", value: money(sprintState.total_profit), className: "cash" },
  ];

  for (const item of items) {
    const div = document.createElement("div");
    div.className = `stat ${item.className}`;
    div.innerHTML = `<div>${item.label}</div><div>${item.value}</div>`;
    progressStatsEl.appendChild(div);
  }
  dayBriefEl.textContent = sprintState.day_brief || "";
}

function renderOffers() {
  offersEl.innerHTML = "";
  if (!sprintState) {
    return;
  }
  if (sprintState.status !== "active") {
    offersEl.innerHTML = '<article class="log-item">Sprint completed. See final evaluation below.</article>';
    return;
  }

  for (const offer of sprintState.offers) {
    const item = document.createElement("article");
    item.className = "log-item";
    item.innerHTML = `
      <strong>${offer.title}</strong>
      <p>${offer.text}</p>
      <p class="meta">Channel: ${offer.channel} | Time: ${offer.time_hours}h | Miles: ${offer.miles} | Risk: ${offer.risk}</p>
      <p class="meta">Cash In: ${money(offer.cash_in)} | Cash Out: ${money(offer.cash_out)}</p>
      <button data-offer-id="${offer.offer_id}">Choose This Option</button>
    `;
    const button = item.querySelector("button");
    button.addEventListener("click", () => chooseOffer(offer.offer_id, offer.title));
    offersEl.appendChild(item);
  }
}

function addDecisionLog(title, chosenProfit, runningProfit) {
  const item = document.createElement("article");
  item.className = "log-item";
  item.innerHTML = `
    <strong>Day decision: ${title}</strong>
    <p class="meta">Net impact from selected option: ${money(chosenProfit)}</p>
    <p class="meta">Running profit: ${money(runningProfit)}</p>
  `;
  decisionLogEl.prepend(item);
}

function renderFinalResult(result) {
  finalResultEl.innerHTML = "";
  const item = document.createElement("article");
  item.className = "log-item";
  item.innerHTML = `
    <strong>Assignment Complete</strong>
    <p class="meta">Student Profit: ${money(result.student_profit)}</p>
    <p class="meta">Optimal Profit (hidden benchmark): ${money(result.optimal_profit)}</p>
    <p class="meta">Success Score: ${result.success_percentage}%</p>
  `;
  finalResultEl.appendChild(item);
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }
  return await res.json();
}

async function startSprint() {
  const playerName = document.getElementById("playerName").value || "Student";
  const totalDays = Number(document.getElementById("totalDays").value || 30);
  const assignmentMinutes = Number(document.getElementById("assignmentMinutes").value || 60);

  const state = await fetchJson(`${API_BASE}/api/strategy/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player_name: playerName,
      total_days: totalDays,
      assignment_minutes: assignmentMinutes,
    }),
  });
  sprintState = state;
  decisionLogEl.innerHTML = "";
  finalResultEl.innerHTML = "";
  renderProgress();
  renderOffers();
}

async function chooseOffer(offerId, title) {
  if (!sprintState || sprintState.status !== "active") {
    return;
  }
  const data = await fetchJson(`${API_BASE}/api/strategy/choose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sprintState.session_id, offer_id: offerId }),
  });
  sprintState = data.state;
  addDecisionLog(title || data.chosen_offer_title, data.chosen_profit, data.running_profit);
  renderProgress();
  renderOffers();

  if (sprintState.status === "completed") {
    const result = await fetchJson(`${API_BASE}/api/strategy/${sprintState.session_id}/result`);
    renderFinalResult(result);
  }
}

startBtn.addEventListener("click", () => {
  startSprint().catch((err) => {
    console.error(err);
    alert(err.message || "Failed to start sprint");
  });
});
