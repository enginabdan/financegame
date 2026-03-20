const loadBtn = document.getElementById("loadBtn");
const overviewEl = document.getElementById("overview");
const sessionsEl = document.getElementById("sessions");
const logsEl = document.getElementById("logs");
const apiBaseInput = document.getElementById("apiBase");
const teacherKeyInput = document.getElementById("teacherKey");
const rememberAccessInput = document.getElementById("rememberAccess");
const defaultApiBase = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";
const STORAGE_API_BASE = "financegame_teacher_api_base";
const STORAGE_TEACHER_KEY = "financegame_teacher_key";
const STORAGE_REMEMBER = "financegame_teacher_remember";

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function renderOverview(overview) {
  overviewEl.innerHTML = "";
  const items = [
    { label: "Total", value: overview.total_sessions, className: "day" },
    { label: "Active", value: overview.active_sessions, className: "cash" },
    { label: "Completed", value: overview.completed_sessions, className: "status" },
    { label: "Failed", value: overview.failed_sessions, className: "stress" },
    { label: "Avg Score", value: overview.avg_score, className: "day" },
  ];

  for (const item of items) {
    const div = document.createElement("div");
    div.className = `stat ${item.className}`;
    div.innerHTML = `<div>${item.label}</div><div>${item.value}</div>`;
    overviewEl.appendChild(div);
  }
}

function renderSessions(sessions, apiBase, teacherKey) {
  sessionsEl.innerHTML = "";

  for (const row of sessions) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.player_name} (${row.city})</strong>
      <p class="meta">Session: ${row.session_id}</p>
      <p class="meta">Status: ${row.status} | Day: ${row.day} | Cash: ${money(row.cash)} | Score: ${row.score}</p>
      <button data-session-id="${row.session_id}">View Day Logs</button>
    `;

    const btn = card.querySelector("button");
    btn.addEventListener("click", () => loadSessionLogs(apiBase, teacherKey, row.session_id));
    sessionsEl.appendChild(card);
  }
}

function renderLogs(logs) {
  logsEl.innerHTML = "";

  for (const row of logs) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>Day ${row.day}: ${row.event_title}</strong>
      <p>${row.event_text}</p>
      <p class="meta">Gross: ${money(row.gross_income)} | Fees: ${money(row.platform_fees)} | Variable: ${money(row.variable_costs)}</p>
      <p class="meta">Household: ${money(row.household_costs)} | Tax reserve: ${money(row.tax_reserve)} | Event: ${money(row.event_cash_impact)}</p>
      <p class="meta">End cash: ${money(row.end_cash)}</p>
    `;
    logsEl.appendChild(card);
  }
}

async function fetchJson(url, teacherKey) {
  const res = await fetch(url, {
    headers: {
      "x-teacher-key": teacherKey,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }

  return await res.json();
}

async function loadDashboard() {
  const apiBase = apiBaseInput.value.trim();
  const teacherKey = teacherKeyInput.value;

  if (!teacherKey) {
    alert("Teacher key is required");
    return;
  }

  if (rememberAccessInput.checked) {
    localStorage.setItem(STORAGE_API_BASE, apiBase);
    localStorage.setItem(STORAGE_TEACHER_KEY, teacherKey);
    localStorage.setItem(STORAGE_REMEMBER, "1");
  } else {
    localStorage.removeItem(STORAGE_API_BASE);
    localStorage.removeItem(STORAGE_TEACHER_KEY);
    localStorage.removeItem(STORAGE_REMEMBER);
  }

  try {
    const [overview, sessions] = await Promise.all([
      fetchJson(`${apiBase}/api/teacher/overview`, teacherKey),
      fetchJson(`${apiBase}/api/teacher/sessions?limit=100`, teacherKey),
    ]);

    renderOverview(overview);
    renderSessions(sessions, apiBase, teacherKey);
    logsEl.innerHTML = "";
  } catch (err) {
    alert(err.message || "Failed to load dashboard");
  }
}

async function loadSessionLogs(apiBase, teacherKey, sessionId) {
  try {
    const logs = await fetchJson(`${apiBase}/api/teacher/sessions/${sessionId}/logs?limit=30`, teacherKey);
    renderLogs(logs);
  } catch (err) {
    alert(err.message || "Failed to load session logs");
  }
}

loadBtn.addEventListener("click", () => {
  loadDashboard().catch((err) => {
    console.error(err);
    alert("Unexpected error while loading dashboard");
  });
});

function restoreAccessFields() {
  const remember = localStorage.getItem(STORAGE_REMEMBER) === "1";
  const savedApiBase = localStorage.getItem(STORAGE_API_BASE);
  const savedTeacherKey = localStorage.getItem(STORAGE_TEACHER_KEY);

  rememberAccessInput.checked = remember;
  apiBaseInput.value = savedApiBase || defaultApiBase;
  if (remember && savedTeacherKey) {
    teacherKeyInput.value = savedTeacherKey;
  }
}

restoreAccessFields();
