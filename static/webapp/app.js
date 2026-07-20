const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");
const restaurantInput = document.getElementById("restaurant");
const descriptionInput = document.getElementById("description");
const photosInput = document.getElementById("photos");
const photoPreview = document.getElementById("photoPreview");
const errorText = document.getElementById("errorText");

// Предзаполняем имя данными из Telegram, если они есть
const tgUser = tg.initDataUnsafe && tg.initDataUnsafe.user;
if (tgUser) {
  const fullName = [tgUser.first_name, tgUser.last_name].filter(Boolean).join(" ");
  if (fullName) nameInput.value = fullName;
}

// Превью выбранных фото
photosInput.addEventListener("change", () => {
  photoPreview.innerHTML = "";
  Array.from(photosInput.files).slice(0, 6).forEach((file) => {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    photoPreview.appendChild(img);
  });
});

function showError(msg) {
  errorText.textContent = msg;
  if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
}

function validate() {
  if (!nameInput.value.trim()) return "Введите имя";
  if (!phoneInput.value.trim()) return "Введите телефон";
  if (!restaurantInput.value.trim()) return "Введите название ресторана";
  if (!descriptionInput.value.trim()) return "Опишите проблему";
  return null;
}

async function submitRequest() {
  const error = validate();
  if (error) {
    showError(error);
    return;
  }
  errorText.textContent = "";

  tg.MainButton.showProgress();
  tg.MainButton.disable();

  const formData = new FormData();
  formData.append("initData", tg.initData);
  formData.append("name", nameInput.value.trim());
  formData.append("phone", phoneInput.value.trim());
  formData.append("restaurant", restaurantInput.value.trim());
  formData.append("description", descriptionInput.value.trim());

  Array.from(photosInput.files).forEach((file) => {
    formData.append("photos", file);
  });

  try {
    const res = await fetch("/api/create_request", {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (data.ok) {
      if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      tg.showPopup(
        {
          title: "Готово ✅",
          message: `Заявка #${data.request_id} отправлена оператору`,
          buttons: [{ type: "ok" }]
        },
        () => tg.close()
      );
    } else {
      showError("Не удалось отправить: " + (data.error || "ошибка сервера"));
      tg.MainButton.hideProgress();
      tg.MainButton.enable();
    }
  } catch (e) {
    showError("Нет соединения с сервером");
    tg.MainButton.hideProgress();
    tg.MainButton.enable();
  }
}

tg.MainButton.setText("Отправить заявку");
tg.MainButton.show();
tg.MainButton.onClick(submitRequest);
