const loadBtn = document.getElementById("loadBtn");
const createClassBtn = document.getElementById("createClassBtn");
const createAssignmentBtn = document.getElementById("createAssignmentBtn");
const loadClassStudentsBtn = document.getElementById("loadClassStudentsBtn");
const loadRubricBtn = document.getElementById("loadRubricBtn");
const exportSessionsCsvBtn = document.getElementById("exportSessionsCsvBtn");
const exportLogsCsvBtn = document.getElementById("exportLogsCsvBtn");
const loadStrategyLeaderboardBtn = document.getElementById("loadStrategyLeaderboardBtn");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");
const bulkDeleteSessionsBtn = document.getElementById("bulkDeleteSessionsBtn");
const bulkDeleteStrategyBtn = document.getElementById("bulkDeleteStrategyBtn");
const loadTrashBtn = document.getElementById("loadTrashBtn");
const bulkRestoreTrashBtn = document.getElementById("bulkRestoreTrashBtn");
const purgeTrashBtn = document.getElementById("purgeTrashBtn");
const purgeOlderTrashBtn = document.getElementById("purgeOlderTrashBtn");
const loadRiskAlertsBtn = document.getElementById("loadRiskAlertsBtn");
const loadAuditBtn = document.getElementById("loadAuditBtn");
const loadEvidenceBtn = document.getElementById("loadEvidenceBtn");

const overviewEl = document.getElementById("overview");
const sessionsEl = document.getElementById("sessions");
const logsEl = document.getElementById("logs");
const classListEl = document.getElementById("classList");
const assignmentListEl = document.getElementById("assignmentList");
const classStudentsListEl = document.getElementById("classStudentsList");
const rubricListEl = document.getElementById("rubricList");
const strategyLeaderboardEl = document.getElementById("strategyLeaderboard");
const strategySessionReviewEl = document.getElementById("strategySessionReview");
const trashListEl = document.getElementById("trashList");
const riskAlertsListEl = document.getElementById("riskAlertsList");
const auditLogListEl = document.getElementById("auditLogList");
const evidenceListEl = document.getElementById("evidenceList");
const trashEntityTypeFilter = document.getElementById("trashEntityTypeFilter");
const trashSinceDaysFilter = document.getElementById("trashSinceDaysFilter");
const trashPurgeOlderDays = document.getElementById("trashPurgeOlderDays");

const apiBaseInput = document.getElementById("apiBase");
const teacherKeyInput = document.getElementById("teacherKey");
const rememberAccessInput = document.getElementById("rememberAccess");
const authEmailInput = document.getElementById("authEmail");
const authPasswordInput = document.getElementById("authPassword");
const authSignInBtn = document.getElementById("authSignInBtn");
const authSignUpBtn = document.getElementById("authSignUpBtn");
const authForgotBtn = document.getElementById("authForgotBtn");
const authSignOutBtn = document.getElementById("authSignOutBtn");
const authStatusEl = document.getElementById("authStatus");
const requiresAuthSections = Array.from(document.querySelectorAll(".requires-auth"));

const classNameInput = document.getElementById("classNameInput");
const assignClassCodeInput = document.getElementById("assignClassCodeInput");
const assignTitleInput = document.getElementById("assignTitleInput");
const assignCityInput = document.getElementById("assignCityInput");
const assignStartCashInput = document.getElementById("assignStartCashInput");
const assignDurationInput = document.getElementById("assignDurationInput");
const assignSprintMinutesInput = document.getElementById("assignSprintMinutesInput");
const classStudentsClassCodeInput = document.getElementById("classStudentsClassCodeInput");
const rubricAssignmentCodeInput = document.getElementById("rubricAssignmentCodeInput");
const filterPlayerNameInput = document.getElementById("filterPlayerName");
const filterClassCodeInput = document.getElementById("filterClassCode");
const filterAssignmentCodeInput = document.getElementById("filterAssignmentCode");
const filterSessionStatusInput = document.getElementById("filterSessionStatus");
const riskClassCodeInput = document.getElementById("riskClassCode");
const riskAssignmentCodeInput = document.getElementById("riskAssignmentCode");
const evidenceClassCodeInput = document.getElementById("evidenceClassCode");
const evidenceAssignmentCodeInput = document.getElementById("evidenceAssignmentCode");
const evidenceStudentIdInput = document.getElementById("evidenceStudentId");
const trashFromDateInput = document.getElementById("trashFromDate");
const trashToDateInput = document.getElementById("trashToDate");
const auditActionFilterInput = document.getElementById("auditActionFilter");
const auditTargetTypeFilterInput = document.getElementById("auditTargetTypeFilter");
const auditFromDateInput = document.getElementById("auditFromDate");
const auditToDateInput = document.getElementById("auditToDate");

const defaultApiBase = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";
const STORAGE_API_BASE = "financegame_teacher_api_base";
const STORAGE_TEACHER_KEY = "financegame_teacher_key";
const STORAGE_REMEMBER = "financegame_teacher_remember";

let currentSessions = [];
let currentSelectedLogs = [];
let currentClasses = [];
let currentAssignments = [];
let currentStrategyRows = [];
let allSessions = [];
let allStrategyRows = [];
let selectedStrategySessionId = null;
const selectedSessionIds = new Set();
const selectedStrategyIds = new Set();
const selectedTrashIds = new Set();

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function getAccess(requireKey = true) {
  const apiBase = apiBaseInput.value.trim();
  const teacherKey = teacherKeyInput.value.trim();
  if (requireKey && !teacherKey) {
    appAlert("Teacher key is required");
    return null;
  }
  return { apiBase, teacherKey };
}

const confirmModalEl = document.getElementById("confirmModal");
const confirmModalTitleEl = document.getElementById("confirmModalTitle");
const confirmModalMessageEl = document.getElementById("confirmModalMessage");
const confirmModalCancelBtn = document.getElementById("confirmModalCancel");
const confirmModalAcceptBtn = document.getElementById("confirmModalAccept");
const confirmModalBackdrop = confirmModalEl?.querySelector("[data-close-confirm]");
const confirmModalCardEl = confirmModalEl?.querySelector(".confirm-modal__card");
const nativeAlert = window.alert.bind(window);
let toastStackEl = null;

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
  if (text.includes("created") || text.includes("saved") || text.includes("joined") || text.includes("copied")) {
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

function showConfirmDialog({
  title = "Please Confirm",
  message = "Are you sure?",
  confirmText = "Confirm",
  cancelText = "Cancel",
  danger = false,
} = {}) {
  if (!confirmModalEl || !confirmModalTitleEl || !confirmModalMessageEl || !confirmModalCancelBtn || !confirmModalAcceptBtn) {
    return Promise.resolve(confirm(message));
  }

  applyModalType(danger ? "warning" : "info");
  confirmModalTitleEl.textContent = title;
  confirmModalMessageEl.textContent = message;
  confirmModalAcceptBtn.textContent = confirmText;
  confirmModalCancelBtn.textContent = cancelText;
  confirmModalAcceptBtn.classList.toggle("danger", danger);
  confirmModalAcceptBtn.classList.toggle("warn", !danger);
  confirmModalEl.hidden = false;
  document.body.style.overflow = "hidden";

  return new Promise((resolve) => {
    const cleanup = () => {
      confirmModalEl.hidden = true;
      document.body.style.overflow = "";
      applyModalType("info");
      confirmModalAcceptBtn.removeEventListener("click", onAccept);
      confirmModalCancelBtn.removeEventListener("click", onCancel);
      confirmModalBackdrop?.removeEventListener("click", onCancel);
      document.removeEventListener("keydown", onKeyDown);
    };
    const onAccept = () => {
      cleanup();
      resolve(true);
    };
    const onCancel = () => {
      cleanup();
      resolve(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        onCancel();
      } else if (event.key === "Enter") {
        onAccept();
      }
    };

    confirmModalAcceptBtn.addEventListener("click", onAccept);
    confirmModalCancelBtn.addEventListener("click", onCancel);
    confirmModalBackdrop?.addEventListener("click", onCancel);
    document.addEventListener("keydown", onKeyDown);
    confirmModalCancelBtn.focus();
  });
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
  currentClasses = classes;
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
      <div class="actions-row">
        <button data-action="copy-class" data-class-code="${cls.class_code}" class="secondary">Copy Class Code</button>
        <button data-action="use-class" data-class-code="${cls.class_code}">Use in Assignment Form</button>
        <button data-action="edit-class" data-class-code="${cls.class_code}" class="warn">Edit Name</button>
        <button data-action="delete-class" data-class-code="${cls.class_code}" class="danger">Delete Class</button>
      </div>
    `;
    classListEl.appendChild(card);
  }
}

function renderAssignments(assignments) {
  currentAssignments = assignments;
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
      <p class="meta">Sprint Pace: ${item.sprint_minutes_per_day} min/day (${item.sprint_minutes_per_day * 30} min total for 30 days)</p>
      <p class="meta">Enrolled Students: ${item.enrolled_sessions} | Active: ${item.is_active ? "Yes" : "No"}</p>
      <div class="actions-row">
        <button data-action="copy-assign-class" data-value="${item.class_code}" class="secondary">Copy Class Code</button>
        <button data-action="copy-assign-code" data-value="${item.assignment_code}" class="secondary">Copy Assignment Code</button>
        <button data-action="edit-assignment" data-assignment-code="${item.assignment_code}" class="warn">Edit Assignment</button>
        <button data-action="toggle-assignment" data-assignment-code="${item.assignment_code}" data-assignment-active="${item.is_active}">${item.is_active ? "Deactivate" : "Activate"}</button>
        <button data-action="delete-assignment" data-assignment-code="${item.assignment_code}" class="danger">Delete Assignment</button>
      </div>
    `;
    assignmentListEl.appendChild(card);
  }
}

function renderClassStudents(classCode, rows) {
  if (!classStudentsListEl) {
    return;
  }
  classStudentsListEl.innerHTML = "";
  if (!rows.length) {
    classStudentsListEl.innerHTML = '<article class="log-item">No students joined this class yet.</article>';
    return;
  }

  for (const row of rows) {
    const fullName = `${row.first_name || ""} ${row.last_name || ""}`.trim() || row.student_id;
    const nextStatus = row.status === "inactive" ? "active" : "inactive";
    const toggleLabel = row.status === "inactive" ? "Set Active" : "Set Inactive";
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${fullName}</strong>
      <p class="meta">Student ID: ${row.student_id} | Status: ${row.status}</p>
      <p class="meta">Email: ${row.school_email || "-"}</p>
      <p class="meta">Joined: ${new Date(row.joined_at).toLocaleString()}</p>
      <div class="actions-row">
        <button data-action="toggle-class-student" data-next-status="${nextStatus}" data-class-code="${classCode}" data-student-id="${row.student_id}" class="warn">${toggleLabel}</button>
        <button data-action="remove-class-student" data-class-code="${classCode}" data-student-id="${row.student_id}" class="danger">Remove Student</button>
      </div>
    `;
    classStudentsListEl.appendChild(card);
  }
}

function renderSessions(sessions) {
  currentSessions = sessions;
  sessionsEl.innerHTML = "";

  if (!sessions.length) {
    sessionsEl.innerHTML = '<article class="log-item">No sessions yet.</article>';
    return;
  }

  for (const row of sessions) {
    const classMeta = row.class_code ? ` | Class: ${row.class_code}` : "";
    const assignMeta = row.assignment_code ? ` | Assignment: ${row.assignment_code}` : "";

    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.player_name} (${row.city})</strong>
      <p class="meta">Session: ${row.session_id}</p>
      <p class="meta">Status: ${row.status} | Day: ${row.day} | Cash: ${money(row.cash)} | Score: ${row.score}${classMeta}${assignMeta}</p>
      <div class="actions-row">
        <label class="inline-check"><input type="checkbox" data-action="select-session" data-session-id="${row.session_id}" ${selectedSessionIds.has(row.session_id) ? "checked" : ""} /> Select</label>
        <button data-action="view-logs" data-session-id="${row.session_id}">View Day Logs</button>
        ${row.class_code ? `<button data-action="remove-from-class" data-session-id="${row.session_id}" class="warn">Remove From Class</button>` : ""}
        <button data-action="edit-session" data-session-id="${row.session_id}" class="warn">Edit Session</button>
        <button data-action="delete-session" data-session-id="${row.session_id}" class="danger">Delete Session</button>
      </div>
    `;

    sessionsEl.appendChild(card);
  }
}

function renderLogs(logs) {
  currentSelectedLogs = logs;
  logsEl.innerHTML = "";

  if (!logs.length) {
    logsEl.innerHTML = '<article class="log-item">No day logs found for this session.</article>';
    return;
  }

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

function renderRubric(rows) {
  rubricListEl.innerHTML = "";
  if (!rows.length) {
    rubricListEl.innerHTML = '<article class="log-item">No student sessions found for this assignment yet.</article>';
    return;
  }

  for (const row of rows) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.player_name} - ${row.letter_grade}</strong>
      <p class="meta">Score: ${row.score} | Band: ${row.performance_band}</p>
      <p class="meta">Day: ${row.day} | Cash: ${money(row.cash)} | Debt: ${money(row.debt)} | Stress: ${row.stress} | Status: ${row.status}</p>
      <p class="meta">Session: ${row.session_id}</p>
    `;
    rubricListEl.appendChild(card);
  }
}

function renderStrategyLeaderboard(rows) {
  currentStrategyRows = rows;
  if (!strategyLeaderboardEl) {
    return;
  }
  strategyLeaderboardEl.innerHTML = "";
  if (!rows.length) {
    strategyLeaderboardEl.innerHTML = '<article class="log-item">No sprint sessions yet.</article>';
    return;
  }

  for (const row of rows) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.player_name} (${row.status})</strong>
      <p class="meta">Progress: Day ${row.current_day}/${row.total_days} | Success: ${row.success_percentage}%</p>
      <p class="meta">Profit: ${money(row.total_profit)} | Optimal: ${money(row.optimal_profit)}</p>
      <p class="meta">Session: ${row.session_id}</p>
      <div class="actions-row">
        <label class="inline-check"><input type="checkbox" data-action="select-strategy" data-session-id="${row.session_id}" ${selectedStrategyIds.has(row.session_id) ? "checked" : ""} /> Select</label>
        <button data-action="view-strategy" data-session-id="${row.session_id}">View Full Decisions</button>
        <button data-action="delete-strategy" data-session-id="${row.session_id}" class="danger">Delete Sprint Session</button>
      </div>
    `;
    strategyLeaderboardEl.appendChild(card);
  }
}

function renderStrategySessionReview(review) {
  if (!strategySessionReviewEl) {
    return;
  }

  strategySessionReviewEl.innerHTML = "";
  if (!review) {
    strategySessionReviewEl.innerHTML = '<article class="log-item">Select a sprint session to see all offers and decisions.</article>';
    return;
  }

  const summary = document.createElement("article");
  summary.className = "log-item";
  summary.innerHTML = `
    <strong>${review.player_name} - Sprint Review</strong>
    <p class="meta">Session: ${review.session_id}</p>
    <p class="meta">Status: ${review.status} | Progress: Day ${review.current_day}/${review.total_days}</p>
    <p class="meta">Total Profit: ${money(review.total_profit)} | Optimal: ${money(review.optimal_profit)} | Success: ${review.success_percentage}%</p>
    <p class="meta">Selected Decisions: ${review.selected_count}</p>
  `;
  strategySessionReviewEl.appendChild(summary);

  if (!review.decisions.length) {
    const empty = document.createElement("article");
    empty.className = "log-item";
    empty.textContent = "No decisions have been made yet in this sprint session.";
    strategySessionReviewEl.appendChild(empty);
    return;
  }

  for (const decision of review.decisions) {
    const card = document.createElement("article");
    card.className = "log-item";

    const offersList = decision.offers
      .map((offer) => {
        const selected = offer.offer_id === decision.chosen_offer_id ? " (Chosen)" : "";
        return `<li>${offer.title}${selected} - Expected: ${money(offer.expected_profit)} | In: ${money(offer.cash_in)} | Out: ${money(offer.cash_out)} | ${offer.channel} | ${offer.risk}</li>`;
      })
      .join("");

    card.innerHTML = `
      <strong>Day ${decision.day}: ${decision.chosen_offer_title}</strong>
      <p class="meta">Chosen Profit: ${money(decision.chosen_profit)} | Best Possible: ${money(decision.optimal_profit)} | Missed: ${money(decision.gap_to_optimal)}</p>
      <p class="meta">Brief: ${decision.day_brief || "-"}</p>
      <details>
        <summary>Show all offered options for this day</summary>
        <ul>${offersList}</ul>
      </details>
    `;
    strategySessionReviewEl.appendChild(card);
  }
}

function renderTrash(items) {
  if (!trashListEl) {
    return;
  }
  trashListEl.innerHTML = "";
  if (!items.length) {
    trashListEl.innerHTML = '<article class="log-item">Trash is empty.</article>';
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${item.entity_type}</strong>
      <p class="meta">Key: ${item.entity_key}</p>
      <p class="meta">Deleted At: ${new Date(item.deleted_at).toLocaleString()}</p>
      <div class="actions-row">
        <label class="inline-check"><input type="checkbox" data-action="select-trash" data-trash-id="${item.id}" ${selectedTrashIds.has(item.id) ? "checked" : ""} /> Select</label>
        <button data-action="restore-trash" data-trash-id="${item.id}" class="secondary">Restore</button>
      </div>
    `;
    trashListEl.appendChild(card);
  }
}

function riskColorClass(level) {
  if (level === "critical") return "danger";
  if (level === "high") return "warn";
  if (level === "medium") return "secondary";
  return "";
}

function renderRiskAlerts(items) {
  if (!riskAlertsListEl) {
    return;
  }
  riskAlertsListEl.innerHTML = "";
  if (!items.length) {
    riskAlertsListEl.innerHTML = '<article class="log-item">No medium/high risk sessions found.</article>';
    return;
  }
  for (const row of items) {
    const card = document.createElement("article");
    card.className = "log-item";
    const reasons = (row.reasons || []).join(", ");
    card.innerHTML = `
      <strong>${row.player_name} (${row.risk_level.toUpperCase()})</strong>
      <p class="meta">Risk Score: ${row.risk_score} | Status: ${row.status} | Day: ${row.day}</p>
      <p class="meta">Cash: ${money(row.cash)} | Debt: ${money(row.debt)} | Stress: ${row.stress} | Score: ${row.score}</p>
      <p class="meta">Class: ${row.class_code || "-"} | Assignment: ${row.assignment_code || "-"}</p>
      <p class="meta">Reasons: ${reasons || "-"}</p>
      <div class="actions-row">
        <button data-action="view-risk-session-logs" data-session-id="${row.session_id}" class="${riskColorClass(row.risk_level)}">View Session Logs</button>
      </div>
    `;
    riskAlertsListEl.appendChild(card);
  }
}

function renderAuditLog(items) {
  if (!auditLogListEl) {
    return;
  }
  auditLogListEl.innerHTML = "";
  if (!items.length) {
    auditLogListEl.innerHTML = '<article class="log-item">No audit records found for selected filters.</article>';
    return;
  }
  for (const row of items) {
    const card = document.createElement("article");
    card.className = "log-item";
    card.innerHTML = `
      <strong>${row.action}</strong>
      <p class="meta">Target: ${row.target_type} / ${row.target_key}</p>
      <p class="meta">Actor: ${row.actor} | Time: ${new Date(row.created_at).toLocaleString()}</p>
    `;
    auditLogListEl.appendChild(card);
  }
}

function renderEvidence(items) {
  if (!evidenceListEl) {
    return;
  }
  evidenceListEl.innerHTML = "";
  if (!items.length) {
    evidenceListEl.innerHTML = '<article class="log-item">No evidence found for selected filters.</article>';
    return;
  }
  for (const row of items) {
    const card = document.createElement("article");
    card.className = "log-item";
    const createdAt = row.created_at ? new Date(row.created_at).toLocaleString() : "-";
    const sizeKb = Math.round((Number(row.size_bytes || 0) / 1024) * 10) / 10;
    card.innerHTML = `
      <strong>${row.filename || "file"}</strong>
      <p class="meta">Student: ${row.student_id || "-"} | Class: ${row.class_code || "-"} | Assignment: ${row.assignment_code || "-"}</p>
      <p class="meta">Uploaded: ${createdAt} | Size: ${sizeKb} KB | Type: ${row.content_type || "-"}</p>
      <p>${row.note || ""}</p>
      <div class="actions-row">
        <button data-action="download-evidence" data-evidence-id="${row.evidence_id}" class="secondary btn-no-margin">Download</button>
        <button data-action="delete-evidence" data-evidence-id="${row.evidence_id}" class="danger btn-no-margin">Delete</button>
      </div>
    `;
    evidenceListEl.appendChild(card);
  }
}

function applySessionFilters() {
  const player = (filterPlayerNameInput?.value || "").trim().toLowerCase();
  const classCode = (filterClassCodeInput?.value || "").trim().toUpperCase();
  const assignmentCode = (filterAssignmentCodeInput?.value || "").trim().toUpperCase();
  const status = (filterSessionStatusInput?.value || "").trim().toLowerCase();

  const filtered = allSessions.filter((row) => {
    if (player && !row.player_name.toLowerCase().includes(player)) return false;
    if (classCode && (row.class_code || "").toUpperCase() !== classCode) return false;
    if (assignmentCode && (row.assignment_code || "").toUpperCase() !== assignmentCode) return false;
    if (status && (row.status || "").toLowerCase() !== status) return false;
    return true;
  });
  renderSessions(filtered);
}

async function fetchJson(url, teacherKey, options = {}) {
  if (window.FinanceAuth?.refreshIdToken) {
    try {
      await window.FinanceAuth.refreshIdToken();
    } catch (_err) {
      // optional
    }
  }
  const token = window.FinanceAuth?.getIdToken?.() || "";
  const res = await fetch(url, {
    ...options,
    headers: {
      "x-teacher-key": teacherKey,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }

  return await res.json();
}

function updateAuthStatus() {
  if (!authStatusEl) {
    return;
  }
  const email = window.FinanceAuth?.getEmail?.() || "";
  authStatusEl.textContent = email ? `Signed in: ${email}` : "Not signed in.";
  const isSignedIn = Boolean(email);
  for (const section of requiresAuthSections) {
    section.classList.toggle("is-visible", isSignedIn);
  }
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
    appAlert(`Copied: ${value}`);
  } catch (_err) {
    appAlert("Clipboard permission blocked. Copy manually.");
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

async function loadClassStudents() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const classCode = (classStudentsClassCodeInput?.value || "").trim().toUpperCase();
  if (!classCode) {
    appAlert("Class code is required");
    return;
  }
  try {
    const rows = await fetchJson(`${apiBase}/api/teacher/classes/${classCode}/students`, teacherKey);
    renderClassStudents(classCode, rows);
  } catch (err) {
    appAlert(err.message || "Failed to load class students");
  }
}

async function loadDashboard() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  persistAccess(apiBase, teacherKey);

  try {
    const [overview, sessions] = await Promise.all([
      fetchJson(`${apiBase}/api/teacher/overview`, teacherKey),
      fetchJson(`${apiBase}/api/teacher/sessions?limit=100`, teacherKey),
    ]);

    renderOverview(overview);
    allSessions = sessions;
    applySessionFilters();
    await loadClassAndAssignments(apiBase, teacherKey);
    await loadStrategyLeaderboard();
    await loadTrash();
    await loadRiskAlerts();
    await loadAuditLog();
    await loadEvidence();
    renderStrategySessionReview(null);
    logsEl.innerHTML = "";
  } catch (err) {
    appAlert(err.message || "Failed to load dashboard");
  }
}

async function loadSessionLogs(apiBase, teacherKey, sessionId) {
  try {
    const logs = await fetchJson(`${apiBase}/api/teacher/sessions/${sessionId}/logs?limit=90`, teacherKey);
    renderLogs(logs);
  } catch (err) {
    appAlert(err.message || "Failed to load session logs");
  }
}

async function loadAssignmentRubric() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const assignmentCode = rubricAssignmentCodeInput.value.trim().toUpperCase();

  if (!assignmentCode) {
    appAlert("Assignment code is required");
    return;
  }

  try {
    const rows = await fetchJson(`${apiBase}/api/teacher/assignments/${assignmentCode}/rubric?limit=300`, teacherKey);
    renderRubric(rows);
  } catch (err) {
    appAlert(err.message || "Failed to load rubric");
  }
}

async function loadStrategyLeaderboard() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  try {
    const rows = await fetchJson(`${apiBase}/api/teacher/strategy/leaderboard?limit=100`, teacherKey);
    allStrategyRows = rows;
    renderStrategyLeaderboard(allStrategyRows);
  } catch (err) {
    console.error(err);
  }
}

async function loadTrash() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  try {
    const params = new URLSearchParams();
    params.set("limit", "200");
    const entityType = (trashEntityTypeFilter?.value || "").trim();
    const sinceDaysRaw = Number(trashSinceDaysFilter?.value || 0);
    if (entityType) {
      params.set("entity_type", entityType);
    }
    if (Number.isFinite(sinceDaysRaw) && sinceDaysRaw > 0) {
      params.set("since_days", String(Math.round(sinceDaysRaw)));
    }
    const fromDate = (trashFromDateInput?.value || "").trim();
    const toDate = (trashToDateInput?.value || "").trim();
    if (fromDate) {
      params.set("from_date", new Date(fromDate).toISOString());
    }
    if (toDate) {
      params.set("to_date", new Date(toDate).toISOString());
    }
    const items = await fetchJson(`${apiBase}/api/teacher/trash?${params.toString()}`, teacherKey);
    renderTrash(items);
  } catch (err) {
    console.error(err);
  }
}

async function loadRiskAlerts() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  try {
    const params = new URLSearchParams();
    params.set("limit", "150");
    const classCode = (riskClassCodeInput?.value || "").trim().toUpperCase();
    const assignmentCode = (riskAssignmentCodeInput?.value || "").trim().toUpperCase();
    if (classCode) {
      params.set("class_code", classCode);
    }
    if (assignmentCode) {
      params.set("assignment_code", assignmentCode);
    }
    const items = await fetchJson(`${apiBase}/api/teacher/risk-alerts?${params.toString()}`, teacherKey);
    renderRiskAlerts(items);
  } catch (err) {
    console.error(err);
    appAlert(err.message || "Failed to load risk alerts");
  }
}

async function loadAuditLog() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  try {
    const params = new URLSearchParams();
    params.set("limit", "500");
    const action = (auditActionFilterInput?.value || "").trim();
    const targetType = (auditTargetTypeFilterInput?.value || "").trim();
    const fromDate = (auditFromDateInput?.value || "").trim();
    const toDate = (auditToDateInput?.value || "").trim();
    if (action) {
      params.set("action", action);
    }
    if (targetType) {
      params.set("target_type", targetType);
    }
    if (fromDate) {
      params.set("from_date", new Date(fromDate).toISOString());
    }
    if (toDate) {
      params.set("to_date", new Date(toDate).toISOString());
    }
    const items = await fetchJson(`${apiBase}/api/teacher/audit?${params.toString()}`, teacherKey);
    renderAuditLog(items);
  } catch (err) {
    console.error(err);
    appAlert(err.message || "Failed to load audit log");
  }
}

async function loadEvidence() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  try {
    const params = new URLSearchParams();
    params.set("limit", "200");
    const classCode = (evidenceClassCodeInput?.value || "").trim().toUpperCase();
    const assignmentCode = (evidenceAssignmentCodeInput?.value || "").trim().toUpperCase();
    const studentId = (evidenceStudentIdInput?.value || "").trim().toUpperCase();
    if (classCode) {
      params.set("class_code", classCode);
    }
    if (assignmentCode) {
      params.set("assignment_code", assignmentCode);
    }
    if (studentId) {
      params.set("student_id", studentId);
    }
    const items = await fetchJson(`${apiBase}/api/teacher/evidence?${params.toString()}`, teacherKey);
    renderEvidence(items);
  } catch (err) {
    console.error(err);
    appAlert(err.message || "Failed to load evidence");
  }
}

async function downloadEvidence(evidenceId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const res = await fetch(`${apiBase}/api/teacher/evidence/${encodeURIComponent(evidenceId)}/download`, {
    headers: { "x-teacher-key": teacherKey },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Evidence download failed");
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename=\"?([^"]+)\"?/i);
  const filename = filenameMatch?.[1] || "evidence.bin";
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

async function deleteEvidence(evidenceId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const confirmDelete = await showConfirmDialog({
    title: "Delete Evidence",
    message: `Delete evidence ${evidenceId}?`,
    confirmText: "Delete",
    cancelText: "Cancel",
    danger: true,
  });
  if (!confirmDelete) {
    return;
  }
  const { apiBase, teacherKey } = access;
  await fetchJson(`${apiBase}/api/teacher/evidence/${encodeURIComponent(evidenceId)}`, teacherKey, { method: "DELETE" });
  appAlert("Evidence deleted.", "Success", "success");
  await loadEvidence();
}

async function loadStrategySessionReview(sessionId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  try {
    const review = await fetchJson(`${apiBase}/api/teacher/strategy/sessions/${sessionId}`, teacherKey);
    selectedStrategySessionId = sessionId;
    renderStrategySessionReview(review);
  } catch (err) {
    appAlert(err.message || "Failed to load strategy session review");
  }
}

function toCsvValue(value) {
  const text = String(value ?? "");
  if (text.includes(",") || text.includes('"') || text.includes("\n")) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function downloadCsv(filename, headers, rows) {
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(row.map(toCsvValue).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportSessionsCsv() {
  if (!currentSessions.length) {
    appAlert("Load dashboard first to export sessions.");
    return;
  }
  downloadCsv(
    "financegame_sessions.csv",
    ["session_id", "player_name", "city", "status", "day", "cash", "stress", "score", "class_code", "assignment_code"],
    currentSessions.map((row) => [
      row.session_id,
      row.player_name,
      row.city,
      row.status,
      row.day,
      row.cash,
      row.stress,
      row.score,
      row.class_code || "",
      row.assignment_code || "",
    ]),
  );
}

function exportLogsCsv() {
  if (!currentSelectedLogs.length) {
    appAlert("Select a session and load day logs first.");
    return;
  }
  downloadCsv(
    "financegame_day_logs.csv",
    [
      "day",
      "event_title",
      "event_text",
      "gross_income",
      "platform_fees",
      "variable_costs",
      "household_costs",
      "tax_reserve",
      "event_cash_impact",
      "end_cash",
      "created_at",
    ],
    currentSelectedLogs.map((row) => [
      row.day,
      row.event_title,
      row.event_text,
      row.gross_income,
      row.platform_fees,
      row.variable_costs,
      row.household_costs,
      row.tax_reserve,
      row.event_cash_impact,
      row.end_cash,
      row.created_at,
    ]),
  );
}

async function createClassroom() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const className = classNameInput.value.trim();

  if (!className) {
    appAlert("Class name is required");
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
    appAlert(`Class created. Code: ${cls.class_code}`);
  } catch (err) {
    appAlert(err.message || "Failed to create class");
  }
}

async function createAssignment() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  const classCode = assignClassCodeInput.value.trim().toUpperCase();
  const title = assignTitleInput.value.trim();
  const city = assignCityInput.value.trim() || "Charlotte, NC";
  const startCash = Number(assignStartCashInput.value || 1800);
  const durationDays = Number(assignDurationInput.value || 30);
  const sprintMinutesPerDay = Number(assignSprintMinutesInput.value || 2);

  if (!classCode || !title) {
    appAlert("Class code and assignment title are required");
    return;
  }
  if (!Number.isFinite(sprintMinutesPerDay) || sprintMinutesPerDay < 1 || sprintMinutesPerDay > 10) {
    appAlert("Sprint minutes/day must be between 1 and 10.");
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
        sprint_minutes_per_day: Math.round(sprintMinutesPerDay),
      }),
    });

    assignTitleInput.value = "";
    await loadClassAndAssignments(apiBase, teacherKey);
    appAlert(`Assignment created. Code: ${assignment.assignment_code}`);
  } catch (err) {
    appAlert(err.message || "Failed to create assignment");
  }
}

async function updateClassroom(classCode) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const existing = currentClasses.find((row) => row.class_code === classCode);
  const nextName = prompt("New class name", existing?.class_name || "");
  if (nextName === null) {
    return;
  }
  const clean = nextName.trim();
  if (!clean) {
    appAlert("Class name cannot be empty.");
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/classes/${classCode}`, teacherKey, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_name: clean }),
    });
    await loadClassAndAssignments(apiBase, teacherKey);
  } catch (err) {
    appAlert(err.message || "Failed to update class");
  }
}

async function deleteClassroom(classCode) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  const ok = await showConfirmDialog({
    title: "Delete Class",
    message: `Delete class ${classCode}? This also deletes related assignments and enrollments.`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/classes/${classCode}`, teacherKey, { method: "DELETE" });
    await loadClassAndAssignments(apiBase, teacherKey);
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to delete class");
  }
}

async function editAssignment(assignmentCode) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const existing = currentAssignments.find((row) => row.assignment_code === assignmentCode);
  if (!existing) {
    appAlert("Assignment not found in current list.");
    return;
  }

  const title = prompt("Assignment title", existing.title);
  if (title === null) {
    return;
  }
  const city = prompt("City", existing.city);
  if (city === null) {
    return;
  }
  const startCashRaw = prompt("Start cash", String(existing.start_cash));
  if (startCashRaw === null) {
    return;
  }
  const durationRaw = prompt("Duration days", String(existing.duration_days));
  if (durationRaw === null) {
    return;
  }
  const sprintMinutesRaw = prompt("Sprint minutes per day (1-10)", String(existing.sprint_minutes_per_day || 2));
  if (sprintMinutesRaw === null) {
    return;
  }

  const startCash = Number(startCashRaw);
  const durationDays = Number(durationRaw);
  const sprintMinutesPerDay = Number(sprintMinutesRaw);
  if (!Number.isFinite(startCash) || !Number.isFinite(durationDays) || !Number.isFinite(sprintMinutesPerDay)) {
    appAlert("Start cash, duration, and sprint minutes must be numeric.");
    return;
  }
  if (sprintMinutesPerDay < 1 || sprintMinutesPerDay > 10) {
    appAlert("Sprint minutes/day must be between 1 and 10.");
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/assignments/${assignmentCode}`, teacherKey, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title.trim(),
        city: city.trim(),
        start_cash: startCash,
        duration_days: Math.round(durationDays),
        sprint_minutes_per_day: Math.round(sprintMinutesPerDay),
      }),
    });
    await loadClassAndAssignments(apiBase, teacherKey);
  } catch (err) {
    appAlert(err.message || "Failed to update assignment");
  }
}

async function toggleAssignment(assignmentCode, currentActive) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  try {
    await fetchJson(`${apiBase}/api/teacher/assignments/${assignmentCode}`, teacherKey, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !currentActive }),
    });
    await loadClassAndAssignments(apiBase, teacherKey);
  } catch (err) {
    appAlert(err.message || "Failed to toggle assignment status");
  }
}

async function deleteAssignment(assignmentCode) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  const ok = await showConfirmDialog({
    title: "Delete Assignment",
    message: `Delete assignment ${assignmentCode}?`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/assignments/${assignmentCode}`, teacherKey, { method: "DELETE" });
    await loadClassAndAssignments(apiBase, teacherKey);
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to delete assignment");
  }
}

async function editSession(sessionId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const existing = currentSessions.find((row) => row.session_id === sessionId);
  if (!existing) {
    appAlert("Session not found.");
    return;
  }

  const playerName = prompt("Player name", existing.player_name);
  if (playerName === null) {
    return;
  }
  const city = prompt("City", existing.city);
  if (city === null) {
    return;
  }
  const status = prompt("Status (active/completed/failed)", existing.status);
  if (status === null) {
    return;
  }
  const dayRaw = prompt("Day", String(existing.day));
  if (dayRaw === null) {
    return;
  }
  const cashRaw = prompt("Cash", String(existing.cash));
  if (cashRaw === null) {
    return;
  }
  const stressRaw = prompt("Stress (0-100)", String(existing.stress));
  if (stressRaw === null) {
    return;
  }
  const scoreRaw = prompt("Score (0-100)", String(existing.score));
  if (scoreRaw === null) {
    return;
  }

  const day = Number(dayRaw);
  const cash = Number(cashRaw);
  const stress = Number(stressRaw);
  const score = Number(scoreRaw);
  if (![day, cash, stress, score].every(Number.isFinite)) {
    appAlert("Day, cash, stress, and score must be numeric.");
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/sessions/${sessionId}`, teacherKey, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_name: playerName.trim(),
        city: city.trim(),
        status: status.trim().toLowerCase(),
        day: Math.round(day),
        cash,
        stress: Math.round(stress),
        score: Math.round(score),
      }),
    });
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to update session");
  }
}

async function deleteSession(sessionId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  const ok = await showConfirmDialog({
    title: "Delete Session",
    message: `Delete session ${sessionId}? This also removes daily logs.`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/sessions/${sessionId}`, teacherKey, { method: "DELETE" });
    logsEl.innerHTML = "";
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to delete session");
  }
}

async function removeSessionFromClass(sessionId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ok = await showConfirmDialog({
    title: "Remove Enrollment",
    message: `Remove session ${sessionId} from class assignment enrollment?`,
    confirmText: "Remove",
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/sessions/${sessionId}/enrollment`, teacherKey, {
      method: "DELETE",
    });
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to remove session from class");
  }
}

async function removeClassStudent(classCode, studentId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ok = await showConfirmDialog({
    title: "Remove Student",
    message: `Remove student ${studentId} from class ${classCode}?`,
    confirmText: "Remove",
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/classes/${classCode}/students/${studentId}`, teacherKey, {
      method: "DELETE",
    });
    await loadClassStudents();
  } catch (err) {
    appAlert(err.message || "Failed to remove student from class");
  }
}

async function updateClassStudentStatus(classCode, studentId, status) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ok = await showConfirmDialog({
    title: "Update Student Status",
    message: `Set student ${studentId} as ${status} in class ${classCode}?`,
    confirmText: "Apply",
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/classes/${classCode}/students/${studentId}`, teacherKey, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    await loadClassStudents();
  } catch (err) {
    appAlert(err.message || "Failed to update student status");
  }
}

async function deleteStrategySession(sessionId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;

  const ok = await showConfirmDialog({
    title: "Delete Sprint Session",
    message: `Delete sprint session ${sessionId}? This removes all decision history for this sprint run.`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }

  try {
    await fetchJson(`${apiBase}/api/teacher/strategy/sessions/${sessionId}`, teacherKey, { method: "DELETE" });
    if (selectedStrategySessionId === sessionId) {
      selectedStrategySessionId = null;
      renderStrategySessionReview(null);
    }
    await loadStrategyLeaderboard();
  } catch (err) {
    appAlert(err.message || "Failed to delete sprint session");
  }
}

async function bulkDeleteSessions() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ids = Array.from(selectedSessionIds);
  if (!ids.length) {
    appAlert("Select at least one session.");
    return;
  }
  const ok = await showConfirmDialog({
    title: "Bulk Delete Sessions",
    message: `Delete ${ids.length} selected sessions?`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/sessions/bulk-delete`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    selectedSessionIds.clear();
    logsEl.innerHTML = "";
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to bulk delete sessions");
  }
}

async function bulkDeleteStrategySessions() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ids = Array.from(selectedStrategyIds);
  if (!ids.length) {
    appAlert("Select at least one sprint session.");
    return;
  }
  const ok = await showConfirmDialog({
    title: "Bulk Delete Sprint Sessions",
    message: `Delete ${ids.length} selected sprint sessions?`,
    confirmText: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/strategy/sessions/bulk-delete`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    selectedStrategyIds.clear();
    if (selectedStrategySessionId && ids.includes(selectedStrategySessionId)) {
      selectedStrategySessionId = null;
      renderStrategySessionReview(null);
    }
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to bulk delete sprint sessions");
  }
}

async function restoreTrashItem(trashId) {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  try {
    await fetchJson(`${apiBase}/api/teacher/trash/${trashId}/restore`, teacherKey, {
      method: "POST",
    });
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to restore archived record");
  }
}

async function bulkRestoreTrashItems() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ids = Array.from(selectedTrashIds);
  if (!ids.length) {
    appAlert("Select at least one trash record.");
    return;
  }
  const ok = await showConfirmDialog({
    title: "Restore Records",
    message: `Restore ${ids.length} selected archived record(s)?`,
    confirmText: "Restore",
    danger: false,
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/trash/bulk-restore`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    selectedTrashIds.clear();
    await loadDashboard();
  } catch (err) {
    appAlert(err.message || "Failed to bulk restore trash items");
  }
}

async function purgeTrashItems() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const ids = Array.from(selectedTrashIds);
  if (!ids.length) {
    appAlert("Select at least one trash record.");
    return;
  }
  const ok = await showConfirmDialog({
    title: "Permanent Delete",
    message: `Permanently delete ${ids.length} selected archived record(s)? This cannot be undone.`,
    confirmText: "Delete Forever",
    danger: true,
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/trash/purge`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    selectedTrashIds.clear();
    await loadTrash();
  } catch (err) {
    appAlert(err.message || "Failed to purge trash items");
  }
}

async function purgeOlderTrashItems() {
  const access = getAccess(true);
  if (!access) {
    return;
  }
  const { apiBase, teacherKey } = access;
  const days = Number(trashPurgeOlderDays?.value || 0);
  if (!Number.isFinite(days) || days < 1) {
    appAlert("Enter a valid number of days (>=1).");
    return;
  }
  const safeDays = Math.round(days);
  const ok = await showConfirmDialog({
    title: "Purge Old Trash",
    message: `Permanently delete trash records older than ${safeDays} days?`,
    confirmText: "Purge",
    danger: true,
  });
  if (!ok) {
    return;
  }
  try {
    await fetchJson(`${apiBase}/api/teacher/trash/purge-older`, teacherKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: safeDays }),
    });
    selectedTrashIds.clear();
    await loadTrash();
  } catch (err) {
    appAlert(err.message || "Failed to purge old trash records");
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
    appAlert("Unexpected error while loading dashboard");
  });
});

createClassBtn.addEventListener("click", () => {
  createClassroom().catch((err) => {
    console.error(err);
    appAlert("Unexpected error while creating class");
  });
});

createAssignmentBtn.addEventListener("click", () => {
  createAssignment().catch((err) => {
    console.error(err);
    appAlert("Unexpected error while creating assignment");
  });
});

if (loadClassStudentsBtn) {
  loadClassStudentsBtn.addEventListener("click", () => {
    loadClassStudents().catch((err) => {
      console.error(err);
      appAlert("Unexpected error while loading class students");
    });
  });
}

loadRubricBtn.addEventListener("click", () => {
  loadAssignmentRubric().catch((err) => {
    console.error(err);
    appAlert("Unexpected error while loading rubric");
  });
});

if (loadStrategyLeaderboardBtn) {
  loadStrategyLeaderboardBtn.addEventListener("click", () => {
    loadStrategyLeaderboard().catch((err) => {
      console.error(err);
      appAlert("Unexpected error while loading strategy leaderboard");
    });
  });
}

exportSessionsCsvBtn.addEventListener("click", exportSessionsCsv);
exportLogsCsvBtn.addEventListener("click", exportLogsCsv);
if (applyFiltersBtn) {
  applyFiltersBtn.addEventListener("click", applySessionFilters);
}
if (clearFiltersBtn) {
  clearFiltersBtn.addEventListener("click", () => {
    filterPlayerNameInput.value = "";
    filterClassCodeInput.value = "";
    filterAssignmentCodeInput.value = "";
    filterSessionStatusInput.value = "";
    applySessionFilters();
  });
}
if (bulkDeleteSessionsBtn) {
  bulkDeleteSessionsBtn.addEventListener("click", () => {
    bulkDeleteSessions().catch(() => {});
  });
}
if (bulkDeleteStrategyBtn) {
  bulkDeleteStrategyBtn.addEventListener("click", () => {
    bulkDeleteStrategySessions().catch(() => {});
  });
}
if (loadTrashBtn) {
  loadTrashBtn.addEventListener("click", () => {
    loadTrash().catch(() => {});
  });
}
if (bulkRestoreTrashBtn) {
  bulkRestoreTrashBtn.addEventListener("click", () => {
    bulkRestoreTrashItems().catch(() => {});
  });
}
if (purgeTrashBtn) {
  purgeTrashBtn.addEventListener("click", () => {
    purgeTrashItems().catch(() => {});
  });
}
if (purgeOlderTrashBtn) {
  purgeOlderTrashBtn.addEventListener("click", () => {
    purgeOlderTrashItems().catch(() => {});
  });
}
if (loadRiskAlertsBtn) {
  loadRiskAlertsBtn.addEventListener("click", () => {
    loadRiskAlerts().catch(() => {});
  });
}
if (loadAuditBtn) {
  loadAuditBtn.addEventListener("click", () => {
    loadAuditLog().catch(() => {});
  });
}
if (loadEvidenceBtn) {
  loadEvidenceBtn.addEventListener("click", () => {
    loadEvidence().catch(() => {});
  });
}
if (trashEntityTypeFilter) {
  trashEntityTypeFilter.addEventListener("change", () => {
    loadTrash().catch(() => {});
  });
}

classListEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }

  const action = target.getAttribute("data-action");
  const classCode = target.getAttribute("data-class-code");

  if (action === "copy-class" && classCode) {
    copyText(classCode).catch(() => {});
    return;
  }
  if (action === "use-class" && classCode) {
    assignClassCodeInput.value = classCode;
    if (classStudentsClassCodeInput) {
      classStudentsClassCodeInput.value = classCode;
    }
    return;
  }
  if (action === "edit-class" && classCode) {
    updateClassroom(classCode).catch(() => {});
    return;
  }
  if (action === "delete-class" && classCode) {
    deleteClassroom(classCode).catch(() => {});
  }
});

if (classStudentsListEl) {
  classStudentsListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }

    const action = target.getAttribute("data-action");
    const classCode = target.getAttribute("data-class-code");
    const studentId = target.getAttribute("data-student-id");
    if (!classCode || !studentId) {
      return;
    }
    if (action === "remove-class-student") {
      removeClassStudent(classCode, studentId).catch(() => {});
      return;
    }
    if (action === "toggle-class-student") {
      const nextStatus = target.getAttribute("data-next-status");
      if (!nextStatus) {
        return;
      }
      updateClassStudentStatus(classCode, studentId, nextStatus).catch(() => {});
    }
  });
}

assignmentListEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }

  const action = target.getAttribute("data-action");
  const value = target.getAttribute("data-value");
  const assignmentCode = target.getAttribute("data-assignment-code");

  if ((action === "copy-assign-class" || action === "copy-assign-code") && value) {
    copyText(value).catch(() => {});
    return;
  }
  if (action === "edit-assignment" && assignmentCode) {
    editAssignment(assignmentCode).catch(() => {});
    return;
  }
  if (action === "toggle-assignment" && assignmentCode) {
    const activeRaw = target.getAttribute("data-assignment-active") || "false";
    toggleAssignment(assignmentCode, activeRaw === "true").catch(() => {});
    return;
  }
  if (action === "delete-assignment" && assignmentCode) {
    deleteAssignment(assignmentCode).catch(() => {});
  }
});

sessionsEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  const action = target.getAttribute("data-action");
  const sessionId = target.getAttribute("data-session-id");
  if (!sessionId) {
    return;
  }

  const access = getAccess(true);
  if (!access) {
    return;
  }

  if (action === "view-logs") {
    loadSessionLogs(access.apiBase, access.teacherKey, sessionId).catch(() => {});
    return;
  }
  if (action === "remove-from-class") {
    removeSessionFromClass(sessionId).catch(() => {});
    return;
  }
  if (action === "edit-session") {
    editSession(sessionId).catch(() => {});
    return;
  }
  if (action === "delete-session") {
    deleteSession(sessionId).catch(() => {});
  }
});

sessionsEl.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") {
    return;
  }
  const action = target.getAttribute("data-action");
  const sessionId = target.getAttribute("data-session-id");
  if (action !== "select-session" || !sessionId) {
    return;
  }
  if (target.checked) {
    selectedSessionIds.add(sessionId);
  } else {
    selectedSessionIds.delete(sessionId);
  }
});

if (strategyLeaderboardEl) {
  strategyLeaderboardEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const action = target.getAttribute("data-action");
    const sessionId = target.getAttribute("data-session-id");
    if (!sessionId) {
      return;
    }

    if (action === "view-strategy") {
      loadStrategySessionReview(sessionId).catch(() => {});
      return;
    }
    if (action === "delete-strategy") {
      deleteStrategySession(sessionId).catch(() => {});
    }
  });

  strategyLeaderboardEl.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") {
      return;
    }
    const action = target.getAttribute("data-action");
    const sessionId = target.getAttribute("data-session-id");
    if (action !== "select-strategy" || !sessionId) {
      return;
    }
    if (target.checked) {
      selectedStrategyIds.add(sessionId);
    } else {
      selectedStrategyIds.delete(sessionId);
    }
  });
}

if (trashListEl) {
  trashListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const action = target.getAttribute("data-action");
    const trashId = target.getAttribute("data-trash-id");
    if (action === "restore-trash" && trashId) {
      restoreTrashItem(Number(trashId)).catch(() => {});
    }
  });

  trashListEl.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") {
      return;
    }
    const action = target.getAttribute("data-action");
    const trashId = target.getAttribute("data-trash-id");
    if (action !== "select-trash" || !trashId) {
      return;
    }
    const parsed = Number(trashId);
    if (Number.isNaN(parsed)) {
      return;
    }
    if (target.checked) {
      selectedTrashIds.add(parsed);
    } else {
      selectedTrashIds.delete(parsed);
    }
  });
}

if (riskAlertsListEl) {
  riskAlertsListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const action = target.getAttribute("data-action");
    const sessionId = target.getAttribute("data-session-id");
    if (action !== "view-risk-session-logs" || !sessionId) {
      return;
    }
    const access = getAccess(true);
    if (!access) {
      return;
    }
    loadSessionLogs(access.apiBase, access.teacherKey, sessionId).catch(() => {});
  });
}

if (evidenceListEl) {
  evidenceListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const action = target.getAttribute("data-action");
    const evidenceId = target.getAttribute("data-evidence-id");
    if (!evidenceId) {
      return;
    }
    if (action === "download-evidence") {
      downloadEvidence(evidenceId).catch((err) => appAlert(err.message || "Failed to download evidence"));
      return;
    }
    if (action === "delete-evidence") {
      deleteEvidence(evidenceId).catch((err) => appAlert(err.message || "Failed to delete evidence"));
    }
  });
}

if (authSignInBtn) {
  authSignInBtn.addEventListener("click", () => {
    const email = (authEmailInput?.value || "").trim();
    const password = (authPasswordInput?.value || "").trim();
    window.FinanceAuth?.signIn?.(email, password)
      .then(() => {
        updateAuthStatus();
        appAlert("Signed in.", "Success", "success");
      })
      .catch((err) => appAlert(err.message || "Sign in failed"));
  });
}

if (authSignUpBtn) {
  authSignUpBtn.addEventListener("click", () => {
    const email = (authEmailInput?.value || "").trim();
    const password = (authPasswordInput?.value || "").trim();
    window.FinanceAuth?.signUp?.(email, password)
      .then(() => {
        updateAuthStatus();
        appAlert("Account created and signed in.", "Success", "success");
      })
      .catch((err) => appAlert(err.message || "Sign up failed"));
  });
}

if (authForgotBtn) {
  authForgotBtn.addEventListener("click", () => {
    const email = (authEmailInput?.value || "").trim();
    window.FinanceAuth?.sendPasswordReset?.(email)
      .then(() => {
        updateAuthStatus();
        appAlert("Password reset email sent. Check your inbox.", "Success", "success");
      })
      .catch((err) => appAlert(err.message || "Could not send password reset email"));
  });
}

if (authSignOutBtn) {
  authSignOutBtn.addEventListener("click", () => {
    window.FinanceAuth?.signOut?.();
    updateAuthStatus();
    appAlert("Signed out.", "Success", "success");
  });
}

if (window.FinanceAuth?.onChange) {
  window.FinanceAuth.onChange(() => updateAuthStatus());
}

restoreAccessFields();
renderStrategySessionReview(null);
updateAuthStatus();

setInterval(() => {
  if (teacherKeyInput.value.trim()) {
    loadStrategyLeaderboard().catch(() => {});
  }
}, 20000);
