const API_BASE = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";

let sessionId = null;
let dayResults = [];
let studentId = localStorage.getItem("financegame_student_id") || "";

const startBtn = document.getElementById("startBtn");
const registerStudentBtn = document.getElementById("registerStudentBtn");
const joinClassBtn = document.getElementById("joinClassBtn");
const loadMyClassesBtn = document.getElementById("loadMyClassesBtn");
const loadClassAssignmentsBtn = document.getElementById("loadClassAssignmentsBtn");
const joinClassAssignmentBtn = document.getElementById("joinClassAssignmentBtn");
const advanceBtn = document.getElementById("advanceBtn");

const stats = document.getElementById("stats");
const log = document.getElementById("log");
const weeklyReport = document.getElementById("weeklyReport");
const myClassesEl = document.getElementById("myClasses");

const studentDisplayNameInput = document.getElementById("studentDisplayName");
const studentIdReadOnlyInput = document.getElementById("studentIdReadOnly");
const playerNameInput = document.getElementById("playerName");
const cityInput = document.getElementById("city");

const classPlayerNameInput = document.getElementById("classPlayerName");
const classCodeInput = document.getElementById("classCode");
const classNameReadOnlyInput = document.getElementById("classNameReadOnly");
const classAssignmentSelect = document.getElementById("classAssignmentSelect");
const assignmentJoinHint = document.getElementById("assignmentJoinHint");
const confirmModalEl = document.getElementById("confirmModal");
const confirmModalTitleEl = document.getElementById("confirmModalTitle");
const confirmModalMessageEl = document.getElementById("confirmModalMessage");
const confirmModalCancelBtn = document.getElementById("confirmModalCancel");
const confirmModalAcceptBtn = document.getElementById("confirmModalAccept");
const confirmModalBackdrop = confirmModalEl?.querySelector("[data-close-confirm]");
const confirmModalCardEl = confirmModalEl?.querySelector(".confirm-modal__card");
const nativeAlert = window.alert.bind(window);
let toastStackEl = null;

let loadedClassCode = "";
let loadedAssignments = [];

function detectAlertType(message, explicitType) {
  if (explicitType) {
    return explicitType;
  }
  const text = String(message || "").toLowerCase();
  if (text.includes("failed") || text.includes("error") || text.includes("invalid")) {
    return "error";
  }
  if (text.includes("required") || text.includes("select") || text.includes("enter")) {
    return "warning";
  }
  if (text.includes("created") || text.includes("saved") || text.includes("joined")) {
    return "success";
  }
  return "info";
}

function normalizeAlertMessage(message, type) {
  const raw = String(message || "").trim();
  if (!raw) {
    return type === "error" ? "Action failed. Reason: Unknown error." : "Done.";
  }
  if (type === "error") {
    return raw.startsWith("Action failed. Reason:") ? raw : `Action failed. Reason: ${raw}`;
  }
  if (type === "warning") {
    return raw.endsWith(".") ? raw : `${raw}.`;
  }
  if (type === "success") {
    return raw.endsWith(".") ? raw : `${raw}.`;
  }
  return raw;
}

function applyModalType(type) {
  if (!confirmModalCardEl) {
    return;
  }
  confirmModalCardEl.classList.remove("is-success", "is-warning", "is-error");
  if (type === "success") {
    confirmModalCardEl.classList.add("is-success");
  } else if (type === "warning") {
    confirmModalCardEl.classList.add("is-warning");
  } else if (type === "error") {
    confirmModalCardEl.classList.add("is-error");
  }
}

function ensureToastStack() {
  if (toastStackEl) {
    return toastStackEl;
  }
  const existing = document.querySelector(".toast-stack");
  if (existing) {
    toastStackEl = existing;
    return toastStackEl;
  }
  const stack = document.createElement("div");
  stack.className = "toast-stack";
  document.body.appendChild(stack);
  toastStackEl = stack;
  return toastStackEl;
}

function showToast(message, type = "info") {
  const stack = ensureToastStack();
  const toast = document.createElement("article");
  toast.className = `toast ${type === "success" ? "toast-success" : "toast-info"}`;
  toast.textContent = message;
  stack.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, 2600);
}

function appAlert(message, title = "Notice", type = "") {
  if (!confirmModalEl || !confirmModalTitleEl || !confirmModalMessageEl || !confirmModalCancelBtn || !confirmModalAcceptBtn) {
    nativeAlert(message);
    return;
  }

  const resolvedType = detectAlertType(message, type);
  const resolvedTitle =
    title === "Notice"
      ? resolvedType === "success"
        ? "Success"
        : resolvedType === "warning"
          ? "Check Input"
          : resolvedType === "error"
            ? "Operation Failed"
            : "Notice"
      : title;
  const titlePrefix = resolvedType === "success" ? "[OK] " : resolvedType === "warning" ? "[!] " : resolvedType === "error" ? "[ERR] " : "";
  const normalized = normalizeAlertMessage(message, resolvedType);
  if (resolvedType === "success" || resolvedType === "info") {
    showToast(normalized, resolvedType);
    return;
  }
  applyModalType(resolvedType);
  confirmModalTitleEl.textContent = `${titlePrefix}${resolvedTitle}`;
  confirmModalMessageEl.textContent = normalized;
  confirmModalAcceptBtn.textContent = "OK";
  confirmModalCancelBtn.style.display = "none";
  confirmModalAcceptBtn.classList.remove("danger", "warn");
  confirmModalAcceptBtn.classList.add("secondary");
  confirmModalEl.hidden = false;
  document.body.style.overflow = "hidden";

  const cleanup = () => {
    confirmModalEl.hidden = true;
    document.body.style.overflow = "";
    applyModalType("info");
    confirmModalCancelBtn.style.display = "";
    confirmModalAcceptBtn.classList.remove("secondary");
    confirmModalAcceptBtn.classList.add("warn");
    confirmModalAcceptBtn.removeEventListener("click", onClose);
    confirmModalBackdrop?.removeEventListener("click", onClose);
    document.removeEventListener("keydown", onKeyDown);
  };
  const onClose = () => cleanup();
  const onKeyDown = (event) => {
    if (event.key === "Escape" || event.key === "Enter") {
      cleanup();
    }
  };

  confirmModalAcceptBtn.addEventListener("click", onClose);
  confirmModalBackdrop?.addEventListener("click", onClose);
  document.addEventListener("keydown", onKeyDown);
  confirmModalAcceptBtn.focus();
}

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function ensureStudentProfile() {
  if (!studentId) {
    appAlert("Create/Load Student Profile first.");
    return false;
  }
  return true;
}

function syncStudentProfileUI() {
  studentIdReadOnlyInput.value = studentId || "";
}

function saveManualStudentId() {
  const entered = (studentIdReadOnlyInput.value || "").trim().toUpperCase();
  studentId = entered;
  if (studentId) {
    localStorage.setItem("financegame_student_id", studentId);
  } else {
    localStorage.removeItem("financegame_student_id");
  }
}

function renderState(state, score = null) {
  stats.innerHTML = "";

  const cells = [
    { label: "Day", value: `${state.day}/${state.duration_days || 30}`, className: "day" },
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

function renderWeeklyReport() {
  weeklyReport.innerHTML = "";
  if (!dayResults.length) {
    weeklyReport.innerHTML = '<article class="log-item">Weekly summaries will appear every 7 days.</article>';
    return;
  }

  const weeks = [];
  for (let i = 0; i < dayResults.length; i += 7) {
    weeks.push(dayResults.slice(i, i + 7));
  }

  for (let w = 0; w < weeks.length; w += 1) {
    const chunk = weeks[w];
    const completedWeek = chunk.length === 7 || dayResults[dayResults.length - 1].state.status !== "active";
    if (!completedWeek) {
      continue;
    }

    const gross = chunk.reduce((sum, d) => sum + d.result.gross_income, 0);
    const fees = chunk.reduce((sum, d) => sum + d.result.platform_fees, 0);
    const household = chunk.reduce((sum, d) => sum + d.result.household_costs, 0);
    const tax = chunk.reduce((sum, d) => sum + d.result.tax_reserve, 0);
    const avgStress = Math.round(chunk.reduce((sum, d) => sum + d.state.stress, 0) / chunk.length);
    const endCash = chunk[chunk.length - 1].state.cash;
    const avgScore = Math.round(chunk.reduce((sum, d) => sum + d.score, 0) / chunk.length);

    const item = document.createElement("article");
    item.className = "log-item";
    item.innerHTML = `
      <strong>Week ${w + 1} Summary</strong>
      <p class="meta">Gross: ${money(gross)} | Fees: ${money(fees)} | Household: ${money(household)} | Tax Set-Aside: ${money(tax)}</p>
      <p class="meta">End Cash: ${money(endCash)} | Avg Stress: ${avgStress} | Avg Score: ${avgScore}</p>
    `;
    weeklyReport.appendChild(item);
  }
}

function resetRunView() {
  dayResults = [];
  log.innerHTML = "";
  renderWeeklyReport();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }
  return await response.json();
}

async function registerStudent() {
  const displayName = (studentDisplayNameInput.value || "").trim();
  if (!displayName) {
    appAlert("Enter student display name.");
    return;
  }

  const profile = await fetchJson(`${API_BASE}/api/student/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });

  studentId = profile.student_id;
  localStorage.setItem("financegame_student_id", studentId);
  syncStudentProfileUI();
  appAlert(`Student profile ready. Student ID: ${studentId}`);
}

function renderMyClasses(classes) {
  if (!myClassesEl) {
    return;
  }
  myClassesEl.innerHTML = "";
  if (!classes.length) {
    myClassesEl.innerHTML = '<article class="log-item">No joined classes yet.</article>';
    return;
  }

  for (const cls of classes) {
    const item = document.createElement("article");
    item.className = "log-item";
    item.innerHTML = `
      <strong>${cls.class_name}</strong>
      <p class="meta">Class Code: <strong>${cls.class_code}</strong></p>
      <button data-action="use-class" data-class-code="${cls.class_code}" class="secondary">Use This Class</button>
    `;
    myClassesEl.appendChild(item);
  }
}

async function loadMyClasses() {
  if (!ensureStudentProfile()) {
    return;
  }
  const classes = await fetchJson(`${API_BASE}/api/student/me/classes?student_id=${encodeURIComponent(studentId)}`);
  renderMyClasses(classes);
}

async function joinClass() {
  if (!ensureStudentProfile()) {
    return;
  }

  const classCode = (classCodeInput.value || "").trim().toUpperCase();
  if (!classCode) {
    appAlert("Enter class code first.");
    return;
  }

  await fetchJson(`${API_BASE}/api/student/join-class`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: studentId, class_code: classCode }),
  });

  await loadMyClasses();
  appAlert(`Joined class ${classCode}`);
}

async function startFreePlayGame() {
  const playerName = playerNameInput.value || "Student";
  const city = cityInput.value || "Charlotte, NC";

  const state = await fetchJson(`${API_BASE}/api/new-game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: playerName, city }),
  });

  sessionId = state.session_id;
  resetRunView();
  renderState(state);
}

function renderClassAssignments(data) {
  loadedClassCode = data.class_code;
  loadedAssignments = data.assignments || [];
  classNameReadOnlyInput.value = data.class_name || "";

  classAssignmentSelect.innerHTML = "";
  if (!loadedAssignments.length) {
    classAssignmentSelect.innerHTML = '<option value="">No active assignments in this class</option>';
    assignmentJoinHint.textContent = "No active assignments found for this class code yet.";
    return;
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select assignment";
  classAssignmentSelect.appendChild(placeholder);

  for (const item of loadedAssignments) {
    const option = document.createElement("option");
    option.value = item.assignment_code;
    option.textContent = `${item.title} (${item.assignment_code}) - ${item.city} - ${item.duration_days} days`;
    classAssignmentSelect.appendChild(option);
  }

  assignmentJoinHint.textContent = "Select one assignment and start. Only this class's active assignments are listed.";
}

async function loadClassAssignments() {
  if (!ensureStudentProfile()) {
    return;
  }

  const classCode = (classCodeInput.value || "").trim().toUpperCase();
  if (!classCode) {
    appAlert("Enter class code first.");
    return;
  }

  const data = await fetchJson(
    `${API_BASE}/api/student/classes/${classCode}/assignments?student_id=${encodeURIComponent(studentId)}`,
  );
  renderClassAssignments(data);
}

async function joinClassAssignment() {
  if (!ensureStudentProfile()) {
    return;
  }

  const playerName = classPlayerNameInput.value || "Student";
  const classCode = (classCodeInput.value || "").trim().toUpperCase();
  const assignmentCode = (classAssignmentSelect.value || "").trim().toUpperCase();

  if (!classCode) {
    appAlert("Enter class code.");
    return;
  }
  if (!assignmentCode) {
    appAlert("Load and select an assignment first.");
    return;
  }

  if (loadedClassCode && loadedClassCode !== classCode) {
    appAlert("Class code changed. Reload assignments first.");
    return;
  }

  const state = await fetchJson(`${API_BASE}/api/student/join-assignment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: studentId,
      player_name: playerName,
      class_code: classCode,
      assignment_code: assignmentCode,
    }),
  });

  sessionId = state.session_id;
  resetRunView();
  renderState(state);
}

async function advanceDay() {
  if (!sessionId) {
    appAlert("Start a game first.");
    return;
  }

  const allocation = {
    gig_hours: Number(document.getElementById("gigHours").value || 0),
    delivery_hours: Number(document.getElementById("deliveryHours").value || 0),
    marketplace_hours: Number(document.getElementById("marketHours").value || 0),
    insurance_choice: document.getElementById("insuranceChoice").value || "basic",
    car_action: document.getElementById("carAction").value || "keep",
    emergency_fund_contribution: Number(document.getElementById("emergencyFundContribution").value || 0),
  };

  const totalHours = allocation.gig_hours + allocation.delivery_hours + allocation.marketplace_hours;
  if (totalHours > 14) {
    appAlert("Total daily hours cannot exceed 14.");
    return;
  }

  const data = await fetchJson(`${API_BASE}/api/advance-day`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, allocation }),
  });

  dayResults.push(data);
  renderState(data.state, data.score);
  addLog(data.result, data.score);
  renderWeeklyReport();
}

startBtn.addEventListener("click", () => {
  startFreePlayGame().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while starting free play game");
  });
});

registerStudentBtn.addEventListener("click", () => {
  registerStudent().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while creating student profile");
  });
});

joinClassBtn.addEventListener("click", () => {
  joinClass().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while joining class");
  });
});

loadMyClassesBtn.addEventListener("click", () => {
  loadMyClasses().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while loading classes");
  });
});

loadClassAssignmentsBtn.addEventListener("click", () => {
  loadClassAssignments().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while loading class assignments");
  });
});

joinClassAssignmentBtn.addEventListener("click", () => {
  joinClassAssignment().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while joining assignment");
  });
});

advanceBtn.addEventListener("click", () => {
  advanceDay().catch((err) => {
    console.error(err);
    appAlert(err.message || "Unexpected error while advancing day");
  });
});

if (myClassesEl) {
  myClassesEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const action = target.getAttribute("data-action");
    if (action !== "use-class") {
      return;
    }
    const classCode = target.getAttribute("data-class-code") || "";
    classCodeInput.value = classCode;
    classCodeInput.dispatchEvent(new Event("input"));
  });
}

classCodeInput.addEventListener("input", () => {
  classCodeInput.value = (classCodeInput.value || "").toUpperCase().trimStart();
});

if (studentIdReadOnlyInput) {
  studentIdReadOnlyInput.addEventListener("input", () => {
    studentIdReadOnlyInput.value = (studentIdReadOnlyInput.value || "").toUpperCase().trimStart();
  });
  studentIdReadOnlyInput.addEventListener("change", saveManualStudentId);
  studentIdReadOnlyInput.addEventListener("blur", saveManualStudentId);
}

syncStudentProfileUI();
resetRunView();
