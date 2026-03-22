(() => {
const API_BASE = window.__APP_CONFIG__?.API_BASE || "http://127.0.0.1:8000";

const startBtn = document.getElementById("startSprintBtn");
const turnInSprintBtn = document.getElementById("turnInSprintBtn");
const offersEl = document.getElementById("sprintOffers");
const progressStatsEl = document.getElementById("sprintProgressStats");
const dayBriefEl = document.getElementById("sprintDayBrief");
const decisionLogEl = document.getElementById("sprintDecisionLog");
const finalResultEl = document.getElementById("sprintFinalResult");
const confirmModalEl = document.getElementById("confirmModal");
const confirmModalTitleEl = document.getElementById("confirmModalTitle");
const confirmModalMessageEl = document.getElementById("confirmModalMessage");
const confirmModalCancelBtn = document.getElementById("confirmModalCancel");
const confirmModalAcceptBtn = document.getElementById("confirmModalAccept");
const confirmModalBackdrop = confirmModalEl?.querySelector("[data-close-confirm]");
const confirmModalCardEl = confirmModalEl?.querySelector(".confirm-modal__card");
const nativeAlert = window.alert.bind(window);
let toastStackEl = null;

let sprintState = null;
let sprintClassContext = null;

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
  if (sprintClassContext && turnInSprintBtn) {
    const canTurnIn = sprintState.status === "completed" || sprintState.current_day > 1;
    turnInSprintBtn.style.display = canTurnIn ? "" : "none";
  }
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
  if (window.FinanceAuth?.refreshIdToken) {
    try {
      await window.FinanceAuth.refreshIdToken();
    } catch (_err) {
      // optional
    }
  }
  const token = window.FinanceAuth?.getIdToken?.() || "";
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(url, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }
  return await res.json();
}

async function startSprint() {
  const playerName = document.getElementById("sprintPlayerName").value || "Student";
  const assignmentMinutes = Number(document.getElementById("sprintAssignmentMinutes").value || 60);
  sprintClassContext = null;
  if (turnInSprintBtn) {
    turnInSprintBtn.style.display = "none";
  }

  const state = await fetchJson(`${API_BASE}/api/strategy/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player_name: playerName,
      total_days: 30,
      assignment_minutes: assignmentMinutes,
    }),
  });
  sprintState = state;
  decisionLogEl.innerHTML = "";
  finalResultEl.innerHTML = "";
  renderProgress();
  renderOffers();
}

function startClassAssignmentSprint({ state, studentId, classCode, assignmentCode }) {
  sprintClassContext = {
    studentId,
    classCode,
    assignmentCode,
  };
  if (turnInSprintBtn) {
    turnInSprintBtn.style.display = "";
  }
  sprintState = state;
  decisionLogEl.innerHTML = "";
  finalResultEl.innerHTML = "";
  renderProgress();
  renderOffers();
}

async function turnInClassAssignmentSprint() {
  if (!sprintState || !sprintClassContext) {
    appAlert("No class sprint assignment in progress.");
    return;
  }
  const result = await fetchJson(`${API_BASE}/api/student/turn-in-sprint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: sprintClassContext.studentId,
      session_id: sprintState.session_id,
    }),
  });
  const refreshed = await fetchJson(`${API_BASE}/api/strategy/${sprintState.session_id}`);
  sprintState = refreshed;
  renderProgress();
  renderOffers();
  const finalResult = await fetchJson(`${API_BASE}/api/strategy/${sprintState.session_id}/result`);
  renderFinalResult(finalResult);
  appAlert(result.message || "Sprint assignment turned in.", "Success", "success");
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

if (startBtn && offersEl && progressStatsEl && dayBriefEl && decisionLogEl && finalResultEl) {
  startBtn.addEventListener("click", () => {
    startSprint().catch((err) => {
      console.error(err);
      appAlert(err.message || "Failed to start sprint");
    });
  });
}

if (turnInSprintBtn) {
  turnInSprintBtn.addEventListener("click", () => {
    turnInClassAssignmentSprint().catch((err) => {
      console.error(err);
      appAlert(err.message || "Failed to turn in sprint assignment");
    });
  });
}

window.FinanceSprint = {
  startClassAssignmentSprint,
};
})();
