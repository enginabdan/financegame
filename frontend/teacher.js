const loadBtn = document.getElementById("loadBtn");
const createClassBtn = document.getElementById("createClassBtn");
const createAssignmentBtn = document.getElementById("createAssignmentBtn");

const overviewEl = document.getElementById("overview");
const sessionsEl = document.getElementById("sessions");
const logsEl = document.getElementById("logs");
const classListEl = document.getElementById("classList");
const assignmentListEl = document.getElementById("assignmentList");

const apiBaseInput = document.getElementById("apiBase");
const teacherKeyInput = document.getElementById("teacherKey");
const rememberAccessInput = document.getElementById("rememberAccess");

const classNameInput = document.getElementById("classNameInput");
const assignClassCodeInput = document.getElementById("assignClassCodeInput");
const assignTitleInput = document.getElementById("assignTitleInput");
const assignCityInput = document.getElementById("assignCityInput");
const assignStartCashInput = document.getElementById("assignStartCashInput");
const assignDurationInput = document.getElementById("assignDurationInput");

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

function renderClasses(classes) {
  classListEl.innerHTML = "";
  if (!classes.length) {
    classListEl.innerHTML = '<article class="log-item">No classes created yet.</article>';
    return;
  }

  for (const cls of classes) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${cls.class_name}</strong>
      <p class="meta">Class Code: <strong>${cls.class_code}</strong></p>
      <p class="meta">Assignments: ${cls.assignment_count} (Active: ${cls.active_assignment_count})</p>
      <p class="meta">
        <button data-copy="${cls.class_code}" data-kind="class">Copy Class Code</button>
        <button data-use-class="${cls.class_code}" data-kind="class">Use in Assignment Form</button>
      </p>
    `;
    classListEl.appendChild(card);
  }
}

function renderAssignments(assignments) {
  assignmentListEl.innerHTML = "";
  if (!assignments.length) {
    assignmentListEl.innerHTML = '<article class="log-item">No assignments created yet.</article>';
    return;
  }

  for (const item of assignments) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${item.title}</strong>
      <p class="meta">Class: ${item.class_code} | Assignment Code: <strong>${item.assignment_code}</strong></p>
      <p class="meta">City: ${item.city} | Start Cash: ${money(item.start_cash)} | Duration: ${item.duration_days} days</p>
      <p class="meta">Enrolled Students: ${item.enrolled_sessions}</p>
      <p class="meta">
        <button data-copy="${item.class_code}" data-kind="assignment">Copy Class Code</button>
        <button data-copy="${item.assignment_code}" data-kind="assignment">Copy Assignment Code</button>
      </p>
    `;
    assignmentListEl.appendChild(card);
  }
}

function renderSessions(sessions, apiBase, teacherKey) {
  sessionsEl.innerHTML = "";

  for (const row of sessions) {
    const classMeta = row.class_code ? ` | Class: ${row.class_code}` : "";
    const assignMeta = row.assignment_code ? ` | Assignment: ${row.assignment_code}` : "";

    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.player_name} (${row.city})</strong>
      <p class="meta">Session: ${row.session_id}</p>
      <p class="meta">Status: ${row.status} | Day: ${row.day} | Cash: ${money(row.cash)} | Score: ${row.score}${classMeta}${assignMeta}</p>
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

async function fetchJson(url, teacherKey, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      "x-teacher-key": teacherKey,
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }

  return await res.json();
}

function persistAccess(apiBase, teacherKey) {
  if (rememberAccessInput.checked) {
    localStorage.setItem(STORAGE_API_BASE, apiBase);
    localStorage.setItem(STORAGE_TEACHER_KEY, teacherKey);
    localStorage.setItem(STORAGE_REMEMBER, "1");
  } else {
    localStorage.removeItem(STORAGE_API_BASE);
    localStorage.removeItem(STORAGE_TEACHER_KEY);
    localStorage.removeItem(STORAGE_REMEMBER);
  }
}

async function copyText(value) {
  try {
    await navigator.clipboard.writeText(value);
    alert(`Copied: ${value}`);
  } catch (_err) {
    alert("Clipboard permission blocked. Copy manually.");
  }
}

async function loadClassAndAssignments(apiBase, teacherKey) {
  const [classes, assignments] = await Promise.all([
    fetchJson(`${apiBase}/api/teacher/classes`, teacherKey),
    fetchJson(`${apiBase}/api/teacher/assignments`, teacherKey),
  ]);

  renderClasses(classes);
  renderAssignments(assignments);
}

async function loadDashboard() {
  const apiBase = apiBaseInput.value.trim();
  const teacherKey = teacherKeyInput.value;

  if (!teacherKey) {
    alert("Teacher key is required");
    return;
  }

  persistAccess(apiBase, teacherKey);

  try {
    const [overview, sessions] = await Promise.all([
      fetchJson(`${apiBase}/api/teacher/overview`, teacherKey),
      fetchJson(`${apiBase}/api/teacher/sessions?limit=100`, teacherKey),
    ]);

    renderOverview(overview);
    renderSessions(sessions, apiBase, teacherKey);
    await loadClassAndAssignments(apiBase, teacherKey);
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

async function createClassroom() {
  const apiBase = apiBaseInput.value.trim();
  const teacherKey = teacherKeyInput.value;
  const className = classNameInput.value.trim();

  if (!teacherKey) {
    alert("Teacher key is required");
    return;
  }
  if (!className) {
    alert("Class name is required");
    return;
  }

  persistAccess(apiBase, teacherKey);

  try {
    const cls = await fetchJson(`${apiBase}/api/teacher/classes`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_name: className }),
    });

    classNameInput.value = "";
    assignClassCodeInput.value = cls.class_code;
    await loadClassAndAssignments(apiBase, teacherKey);
    alert(`Class created. Code: ${cls.class_code}`);
  } catch (err) {
    alert(err.message || "Failed to create class");
  }
}

async function createAssignment() {
  const apiBase = apiBaseInput.value.trim();
  const teacherKey = teacherKeyInput.value;

  const classCode = assignClassCodeInput.value.trim().toUpperCase();
  const title = assignTitleInput.value.trim();
  const city = assignCityInput.value.trim() || "Charlotte, NC";
  const startCash = Number(assignStartCashInput.value || 1800);
  const durationDays = Number(assignDurationInput.value || 30);

  if (!teacherKey) {
    alert("Teacher key is required");
    return;
  }
  if (!classCode || !title) {
    alert("Class code and assignment title are required");
    return;
  }

  persistAccess(apiBase, teacherKey);

  try {
    const assignment = await fetchJson(`${apiBase}/api/teacher/assignments`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        class_code: classCode,
        title,
        city,
        start_cash: startCash,
        duration_days: durationDays,
      }),
    });

    assignTitleInput.value = "";
    await loadClassAndAssignments(apiBase, teacherKey);
    alert(`Assignment created. Code: ${assignment.assignment_code}`);
  } catch (err) {
    alert(err.message || "Failed to create assignment");
  }
}

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

loadBtn.addEventListener("click", () => {
  loadDashboard().catch((err) => {
    console.error(err);
    alert("Unexpected error while loading dashboard");
  });
});

createClassBtn.addEventListener("click", () => {
  createClassroom().catch((err) => {
    console.error(err);
    alert("Unexpected error while creating class");
  });
});

createAssignmentBtn.addEventListener("click", () => {
  createAssignment().catch((err) => {
    console.error(err);
    alert("Unexpected error while creating assignment");
  });
});

classListEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }

  const copyValue = target.getAttribute("data-copy");
  if (copyValue) {
    copyText(copyValue).catch(() => {});
    return;
  }

  const useClass = target.getAttribute("data-use-class");
  if (useClass) {
    assignClassCodeInput.value = useClass;
  }
});

assignmentListEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  const copyValue = target.getAttribute("data-copy");
  if (copyValue) {
    copyText(copyValue).catch(() => {});
  }
});

restoreAccessFields();
