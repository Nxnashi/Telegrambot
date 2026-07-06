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

modalCancelBtn.addEventListener("click", () => {
  reasonOverlay.hidden = true;
  modalOnConfirm = null;
  loadRequests(); // сбрасываем карточку на место, если её уже перетащили визуально
});

modalConfirmBtn.addEventListener("click", () => {
  const reason = modalReason.value.trim();
  const callback = modalOnConfirm;
  reasonOverlay.hidden = true;
  modalOnConfirm = null;
  if (callback) callback(reason);
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return
