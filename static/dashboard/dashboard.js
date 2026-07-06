const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData;

const listNew = document.getElementById("listNew");
const listProgress = document.getElementById("listProgress");
const listPostponed = document.getElementById("listPostponed");
const listDone = document.getElementById("listDone");
const listCancelled = document.getElementById("listCancelled");

const countNew = document.getElementById("countNew");
const countProgress = document.getElementById("countProgress");
const countPostponed = document.getElementById("countPostponed");
const countDone = document.getElementById("countDone");
const countCancelled = document.getElementById("countCancelled");

const toast = document.getElementById("toast");
const tabs = document.getElementById("tabs");
const boardView = document.getElementById("boardView");
const statsView = document.getElementById("statsView");
const statsTable = document.getElementById("statsTable");
const exportBtn = document.getElementById("exportBtn");

const reasonOverlay = document.getElementById("reasonOverlay");
const modalTitle = document.getElementById("modalTitle");
const modalReason = document.getElementById("modalReason");
const modalCancelBtn = document.getElementById("modalCancelBtn");
const modalConfirmBtn = document.getElementById("modalConfirmBtn");

let isDragging = false;
let isAdmin = false;
let modalOnConfirm = null;

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

function statusToColumn(status) {
  if (status === "Заявка отправлена") return "new";
  if (status === "Заявка в процессе") return "progress";
  if (status === "Отложена") return "postponed";
  if (status === "Отменена") return "cancelled";
  return "done";
}

function openReasonModal(title, onConfirm) {
  modalTitle.textContent = title;
  modalReason.value = "";
  modalOnConfirm = onConfirm;
  reasonOverlay.hidden = false;
}

if (modalCancelBtn) {
  modalCancelBtn.addEventListener("click", () => {
    reasonOverlay.hidden = true;
    modalOnConfirm = null;
    loadRequests(); // сбрасываем карточку на место, если её уже перетащили визуально
  });
}

if (modalConfirmBtn) {
  modalConfirmBtn.addEventListener("click", () => {
    const reason = modalReason.value.trim();
    const callback = modalOnConfirm;
    reasonOverlay.hidden = true;
    modalOnConfirm = null;
    if (callback) callback(reason);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderCard(item, column) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.id = item.id;

  const desc = (item.description || "").slice(0, 120);

  let actions = "";
  if (column === "progress") {
    actions = `
      <div class="card-actions">
        <button class="action-btn" data-action="postpone" data-id="${item.id}">⏸ Отложить</button>
        <button class="action-btn" data-action="cancel" data-id="${item.id}">🚫 Отменить</button>
      </div>`;
  } else if (column === "postponed") {
    actions = `
      <div class="card-actions">
        <button class="action-btn" data-action="resume" data-id="${item.id}">▶️ Возобновить</button>
        <button class="action-btn" data-action="cancel" data-id="${item.id}">🚫 Отменить</button>
      </div>`;
  } else if (column === "cancelled") {
    actions = `
      <div class="card-actions">
        <button class="action-btn" data-action="restore" data-id="${item.id}">↩️ Вернуть</button>
      </div>`;
  }

  const showReason = (item.status === "Отменена" || item.status === "Отложена") && item.reason;

  card.innerHTML = `
    <div class="card-top">
      <span>${escapeHtml(item.restaurant || "")}</span>
      <span class="card-id">#${item.id}</span>
    </div>
    <div class="card-desc">${escapeHtml(desc)}</div>
    ${item.operator_name ? `<div class="card-meta">👨‍💼 ${escapeHtml(item.operator_name)}</div>` : ""}
    ${item.rating ? `<div class="card-meta">⭐ ${escapeHtml(item.rating)}</div>` : ""}
    ${showReason ? `<div class="card-meta">📝 ${escapeHtml(item.reason)}</div>` : ""}
    ${actions}
  `;

  card.addEventListener("click", (e) => {
    if (e.target.closest(".action-btn")) return;
    if (isDragging) return;
    tg.showPopup({
      title: `Заявка #${item.id}`,
      message: [
        item.name ? `Имя: ${item.name}` : null,
        item.phone ? `Телефон: ${item.phone}` : null,
        `Ресторан: ${item.restaurant}`,
        `Статус: ${item.status}`,
        item.operator_name ? `Оператор: ${item.operator_name}` : null,
        item.reason ? `Причина: ${item.reason}` : null,
        "",
        item.description || ""
      ].filter(Boolean).join("\n"),
      buttons: [{ type: "ok" }]
    });
  });

  return card;
}

function toggleEmpty(listEl) {
  listEl.classList.toggle("empty", listEl.children.length === 0);
}

async function loadRequests() {
  try {
    const res = await fetch(`/api/dashboard/requests?initData=${encodeURIComponent(initData)}`);
    const data = await res.json();
    if (!data.ok) {
      showToast("Нет доступа");
      return;
    }

    listNew.innerHTML = "";
    listProgress.innerHTML = "";
    listPostponed.innerHTML = "";
    listDone.innerHTML = "";
    listCancelled.innerHTML = "";

    data.items.forEach((item) => {
      const column = statusToColumn(item.status);
      const card = renderCard(item, column);
      if (column === "new") listNew.appendChild(card);
      else if (column === "progress") listProgress.appendChild(card);
      else if (column === "postponed") listPostponed.appendChild(card);
      else if (column === "cancelled") listCancelled.appendChild(card);
      else listDone.appendChild(card);
    });

    countNew.textContent = listNew.children.length;
    countProgress.textContent = listProgress.children.length;
    countPostponed.textContent = listPostponed.children.length;
    countDone.textContent = listDone.children.length;
    countCancelled.textContent = listCancelled.children.length;

    [listNew, listProgress, listPostponed, listDone, listCancelled].forEach(toggleEmpty);
  } catch (e) {
    showToast("Нет соединения с сервером");
  }
}

async function callTransition(action, id, reason) {
  const formData = new FormData();
  formData.append("initData", initData);
  formData.append("request_id", id);
  if (reason !== undefined) formData.append("reason", reason);

  try {
    const res = await fetch(`/api/dashboard/${action}`, { method: "POST", body: formData });
    const data = await res.json();
    if (!data.ok) {
      showToast(data.message || "Не удалось выполнить действие");
    } else if (tg.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred("success");
    }
    return data.ok;
  } catch (e) {
    showToast("Нет соединения с сервером");
    return false;
  }
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".action-btn");
  if (!btn) return;

  const action = btn.dataset.action;
  const id = btn.dataset.id;

  if (action === "resume") {
    callTransition("resume", id).then(loadRequests);
  } else if (action === "restore") {
    callTransition("restore", id).then(loadRequests);
  } else if (action === "postpone") {
    openReasonModal(`Отложить заявку #${id} — причина`, (reason) => {
      callTransition("postpone", id, reason).then(loadRequests);
    });
  } else if (action === "cancel") {
    openReasonModal(`Отменить заявку #${id} — причина`, (reason) => {
      callTransition("cancel", id, reason).then(loadRequests);
    });
  }
});

const TRANSITIONS = {
  "new->progress": { action: "take" },
  "progress->done": { action: "complete" },
  "progress->postponed": { action: "postpone", needsReason: true },
  "progress->cancelled": { action: "cancel", needsReason: true },
  "postponed->progress": { action: "resume" },
  "postponed->cancelled": { action: "cancel", needsReason: true },
  "cancelled->progress": { action: "restore" },
};

function attachSortable(el) {
  Sortable.create(el, {
    group: "requests",
    animation: 150,
    onStart: () => { isDragging = true; },
    onEnd: async (evt) => {
      isDragging = false;
      const fromStatus = evt.from.closest(".column").dataset.status;
      const toStatus = evt.to.closest(".column").dataset.status;
      const id = evt.item.dataset.id;

      if (fromStatus === toStatus) {
        return;
      }

      const transition = TRANSITIONS[`${fromStatus}->${toStatus}`];

      if (!transition) {
        showToast("Такой переход недоступен");
        loadRequests();
        return;
      }

      if (transition.needsReason) {
        openReasonModal(`Заявка #${id} — причина`, async (reason) => {
          await callTransition(transition.action, id, reason);
          loadRequests();
        });
      } else {
        await callTransition(transition.action, id);
        loadRequests();
      }
    }
  });
}

async function loadStats() {
  const res = await fetch(`/api/dashboard/stats?initData=${encodeURIComponent(initData)}`);
  const data = await res.json();
  if (!data.ok) return;

  statsTable.innerHTML = data.items.map((op) => `
    <div class="stats-card">
      <b>👨‍💼 ${escapeHtml(op.operator_name)}</b>
      <div class="stats-row"><span>Всего</span><span>${op.total}</span></div>
      <div class="stats-row"><span>Выполнено</span><span>${op.done}</span></div>
      <div class="stats-row"><span>⭐⭐⭐ Отлично</span><span>${op.great}</span></div>
      <div class="stats-row"><span>⭐⭐ Нормально</span><span>${op.ok}</span></div>
      <div class="stats-row"><span>⭐ Плохо</span><span>${op.bad}</span></div>
    </div>
  `).join("") || `<p style="color:var(--hint)">Нет данных</p>`;
}

if (tabs) {
  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");

    if (btn.dataset.tab === "board") {
      boardView.hidden = false;
      statsView.hidden = true;
      loadRequests();
    } else {
      boardView.hidden = true;
      statsView.hidden = false;
      loadStats();
    }
  });
}

if (exportBtn) {
  exportBtn.addEventListener("click", () => {
    window.open(`/api/dashboard/export?initData=${encodeURIComponent(initData)}`, "_blank");
  });
}

async function init() {
  [listNew, listProgress, listPostponed, listDone, listCancelled].forEach((el) => {
    if (!el) {
      console.error("dashboard: не найден один из списков-колонок на странице");
      return;
    }
    try {
      attachSortable(el);
    } catch (e) {
      console.error("dashboard attachSortable error:", e);
    }
  });

  try {
    const res = await fetch(`/api/dashboard/me?initData=${encodeURIComponent(initData)}`);
    const data = await res.json();
    if (!data.ok) {
      document.body.innerHTML = "<p style='padding:20px;text-align:center;color:var(--hint)'>Доступ только для операторов</p>";
      return;
    }
    isAdmin = data.is_admin;
    if (tabs) tabs.hidden = !isAdmin;
  } catch (e) {
    console.error("dashboard /me error:", e);
    // если /me не ответил — всё равно пробуем показать доску
  }

  try {
    await loadRequests();
  } catch (e) {
    console.error("dashboard loadRequests error:", e);
  }

  setInterval(() => {
    if (!isDragging && boardView.hidden === false) loadRequests();
  }, 8000);
}

init().catch((e) => console.error("dashboard init error:", e));
