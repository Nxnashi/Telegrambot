const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData;

const listNew = document.getElementById("listNew");
const listProgress = document.getElementById("listProgress");
const listDone = document.getElementById("listDone");
const countNew = document.getElementById("countNew");
const countProgress = document.getElementById("countProgress");
const countDone = document.getElementById("countDone");
const toast = document.getElementById("toast");
const tabs = document.getElementById("tabs");
const boardView = document.getElementById("boardView");
const statsView = document.getElementById("statsView");
const statsTable = document.getElementById("statsTable");
const exportBtn = document.getElementById("exportBtn");

let isDragging = false;
let isAdmin = false;

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

function statusToColumn(status) {
  if (status === "Заявка отправлена") return "new";
  if (status === "Заявка в процессе") return "progress";
  return "done";
}

function renderCard(item) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.id = item.id;

  const desc = (item.description || "").slice(0, 120);

  card.innerHTML = `
    <div class="card-top">
      <span>${escapeHtml(item.restaurant || "")}</span>
      <span class="card-id">#${item.id}</span>
    </div>
    <div class="card-desc">${escapeHtml(desc)}</div>
    ${item.operator_name ? `<div class="card-meta">👨‍💼 ${escapeHtml(item.operator_name)}</div>` : ""}
    ${item.rating ? `<div class="card-meta">⭐ ${escapeHtml(item.rating)}</div>` : ""}
  `;

  card.addEventListener("click", () => {
    if (isDragging) return;
    tg.showPopup({
      title: `Заявка #${item.id}`,
      message: [
        item.name ? `Имя: ${item.name}` : null,
        item.phone ? `Телефон: ${item.phone}` : null,
        `Ресторан: ${item.restaurant}`,
        `Статус: ${item.status}`,
        item.operator_name ? `Оператор: ${item.operator_name}` : null,
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
    listDone.innerHTML = "";

    data.items.forEach((item) => {
      const column = statusToColumn(item.status);
      const card = renderCard(item);
      if (column === "new") listNew.appendChild(card);
      else if (column === "progress") listProgress.appendChild(card);
      else listDone.appendChild(card);
    });

    countNew.textContent = listNew.children.length;
    countProgress.textContent = listProgress.children.length;
    countDone.textContent = listDone.children.length;

    [listNew, listProgress, listDone].forEach(toggleEmpty);
  } catch (e) {
    showToast("Нет соединения с сервером");
  }
}

async function callTransition(action, id) {
  const formData = new FormData();
  formData.append("initData", initData);
  formData.append("request_id", id);

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

      if (fromStatus === toStatus) return;

      let ok = false;
      if (fromStatus === "new" && toStatus === "progress") {
        ok = await callTransition("take", id);
      } else if (fromStatus === "progress" && toStatus === "done") {
        ok = await callTransition("complete", id);
      } else {
        ok = false;
        showToast("Такой переход недоступен");
      }

      loadRequests();
    }
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
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

exportBtn.addEventListener("click", () => {
  window.open(`/api/dashboard/export?initData=${encodeURIComponent(initData)}`, "_blank");
});

async function init() {
  attachSortable(listNew);
  attachSortable(listProgress);
  attachSortable(listDone);

  try {
    const res = await fetch(`/api/dashboard/me?initData=${encodeURIComponent(initData)}`);
    const data = await res.json();
    if (!data.ok) {
      document.body.innerHTML = "<p style='padding:20px;text-align:center;color:var(--hint)'>Доступ только для операторов</p>";
      return;
    }
    isAdmin = data.is_admin;
    tabs.hidden = !isAdmin;
  } catch (e) {
    // если /me не ответил — всё равно пробуем показать доску
  }

  loadRequests();
  setInterval(() => {
    if (!isDragging && boardView.hidden === false) loadRequests();
  }, 8000);
}

init();
