console.log("app.js v4");

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, method = "GET", body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401 && document.body.dataset.page !== "login") {
    location.href = "/login";
    throw new Error("Сессия истекла");
  }
  if (!res.ok) {
    let msg = "Ошибка " + res.status;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

const guard = (fn) => async (...args) => {
  try { await fn(...args); } catch (e) { toast(e.message, "error"); }
};

/* ---------- Тосты ---------- */
function toast(message, type = "info") {
  let wrap = $(".toasts");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toasts";
    document.body.appendChild(wrap);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  wrap.appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 220);
  }, 3500);
}

/* ---------- Модалки ---------- */
function openModal({ title, subtitle = "", body, okText = "Сохранить", cancelText = "Отменить", danger = false, onSubmit }) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
        <h3>${esc(title)}</h3>
        ${subtitle ? `<p class="modal-sub">${esc(subtitle)}</p>` : ""}
        <form>
          <div class="modal-body">${body}</div>
          <p class="modal-error" hidden></p>
          <div class="modal-actions">
            <button type="button" class="btn ghost" data-cancel>${esc(cancelText)}</button>
            <button type="submit" class="btn ${danger ? "danger" : "primary"}" data-ok>${esc(okText)}</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(overlay);
    document.body.classList.add("modal-open");

    const form = overlay.querySelector("form");
    const err = overlay.querySelector(".modal-error");
    const okBtn = overlay.querySelector("[data-ok]");
    let closed = false;

    const close = (result) => {
      if (closed) return;
      closed = true;
      document.removeEventListener("keydown", onKey);
      overlay.classList.add("closing");
      setTimeout(() => {
        overlay.remove();
        if (!$(".modal-overlay")) document.body.classList.remove("modal-open");
      }, 170);
      resolve(result);
    };
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(false); });
    overlay.querySelector("[data-cancel]").onclick = () => close(false);

    form.onsubmit = async (e) => {
      e.preventDefault();
      err.hidden = true;
      okBtn.disabled = true;
      okBtn.classList.add("loading");
      try {
        const result = await onSubmit(new FormData(form), form);
        close(result === undefined ? true : result);
      } catch (ex) {
        err.textContent = ex.message;
        err.hidden = false;
        okBtn.disabled = false;
        okBtn.classList.remove("loading");
      }
    };

    requestAnimationFrame(() => {
      overlay.classList.add("open");
      const first = overlay.querySelector("input, select") || okBtn;
      first.focus();
    });
  });
}

function confirmAction({ title, text, okText = "Да", cancelText = "Нет" }) {
  return openModal({
    title,
    body: `<p class="confirm-text">${esc(text)}</p>`,
    okText, cancelText, danger: true,
    onSubmit: () => true,
  });
}

/* ---------- Общее для страниц ---------- */
let currentUser = null;

function bindCommon(me) {
  currentUser = me;

  const who = $("#whoami");
  if (who) who.textContent = me.username;

  const adminLink = $("#admin-link");
  if (adminLink) adminLink.hidden = me.role !== "admin";

  const scanBtn = $("#scan");
  if (scanBtn) scanBtn.hidden = me.role !== "admin";

  const profileBtn = $("#profile-btn");
  if (profileBtn) profileBtn.onclick = () => openProfileModal();

  const logoutBtn = $("#logout");
  if (logoutBtn) logoutBtn.onclick = guard(async () => {
    await api("/api/auth/logout", "POST");
    location.href = "/login";
  });
}

async function openProfileModal() {
  const me = currentUser;
  await openModal({
    title: "Мой профиль",
    subtitle: "Смена логина и пароля",
    okText: "Сохранить",
    body: `
      <label class="field"><span>Логин</span>
        <input name="username" value="${esc(me.username)}" minlength="3" maxlength="64" required autocomplete="username">
      </label>
      <label class="field"><span>Текущий пароль</span>
        <input name="current_password" type="password" required autocomplete="current-password" placeholder="Обязательно для любых изменений">
      </label>
      <label class="field"><span>Новый пароль</span>
        <input name="new_password" type="password" minlength="6" maxlength="72" autocomplete="new-password" placeholder="Оставьте пустым, чтобы не менять">
      </label>
      <label class="field"><span>Повторите новый пароль</span>
        <input name="new_password2" type="password" minlength="6" maxlength="72" autocomplete="new-password" placeholder="Повтор нового пароля">
      </label>`,
    onSubmit: async (fd) => {
      const username = fd.get("username").trim();
      const current_password = fd.get("current_password");
      const new_password = fd.get("new_password");
      const new_password2 = fd.get("new_password2");
      if (new_password && new_password !== new_password2) throw new Error("Новые пароли не совпадают");
      if (!new_password && new_password2) throw new Error("Введите новый пароль");

      const payload = { current_password };
      let changed = false;
      if (username !== me.username) { payload.username = username; changed = true; }
      if (new_password) { payload.new_password = new_password; changed = true; }
      if (!changed) throw new Error("Измените логин или задайте новый пароль");

      const updated = await api("/api/auth/me", "PATCH", payload);
      currentUser = updated;
      const who = $("#whoami");
      if (who) who.textContent = updated.username;
      toast("Профиль обновлён", "success");
      return true;
    },
  });
}

/* ---------- Логин ---------- */
function initLogin() {
  const form = $("#login-form");
  const error = $("#error");
  const password = $("#password");
  const toggle = $("#toggle-password");

  if (toggle && password) {
    toggle.onclick = () => {
      const show = password.type === "password";
      password.type = show ? "text" : "password";
      toggle.textContent = show ? "🙈" : "👁";
      toggle.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
      password.focus();
    };
  }

  form.addEventListener("input", () => { error.textContent = ""; });

  form.onsubmit = async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    const f = new FormData(form);
    submitBtn.disabled = true;
    submitBtn.classList.add("loading");
    try {
      await api("/api/auth/login", "POST", {
        username: f.get("username"),
        password: f.get("password"),
      });
      location.href = "/";
    } catch (err) {
      error.textContent = err.message;
      submitBtn.disabled = false;
      submitBtn.classList.remove("loading");
    }
  };
}

/* ---------- Дашборд ---------- */
let isAdmin = false;

async function loadControllers() {
  const list = await api("/api/controllers");
  const root = $("#controllers");
  root.innerHTML = "";

  if (!list.length) {
    root.innerHTML = '<div class="empty">Контроллеры не найдены.<br>Дождитесь сканирования сети или нажмите «Сканировать сеть».</div>';
    return;
  }

  const byName = (a, b) => (a.name || a.ip).localeCompare(b.name || b.ip, "ru");
  const active = list.filter((c) => c.is_online).sort(byName);
  const inactive = list.filter((c) => !c.is_online).sort(byName);

  root.appendChild(renderSection("В сети", active));
  if (inactive.length) root.appendChild(renderSection("Не в сети", inactive));
}

function renderSection(title, controllers) {
  const section = document.createElement("section");
  section.className = "listing-section";
  section.innerHTML = `<h2 class="section-title">${esc(title)} <span class="count">${controllers.length}</span></h2>`;
  const grid = document.createElement("div");
  grid.className = "grid";
  if (!controllers.length) {
    grid.innerHTML = '<div class="empty">Устройств в этой группе пока нет</div>';
  } else {
    for (const c of controllers) grid.appendChild(renderCard(c));
  }
  section.appendChild(grid);
  return section;
}

function renderCard(c) {
  const card = document.createElement("section");
  card.className = "card" + (c.is_online ? "" : " offline");
  card.innerHTML = `
    <div class="card-head">
      <div class="card-title">
        <span class="status-dot ${c.is_online ? "on" : "off"}"></span>
        <h2>${esc(c.name || c.ip)}</h2>
      </div>
      <div class="card-meta">
        <span class="ip">${esc(c.ip)}</span>
        ${isAdmin ? '<button class="icon-btn danger" data-del title="Удалить контроллер" aria-label="Удалить контроллер">🗑</button>' : ""}
      </div>
    </div>
    <div class="card-actions">
      <button class="btn small" data-on ${c.is_online ? "" : "disabled"}>Включить все</button>
      <button class="btn small ghost" data-off ${c.is_online ? "" : "disabled"}>Выключить все</button>
    </div>
    <ul class="relays"></ul>`;

  const ul = card.querySelector(".relays");
  for (const r of c.relays) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(r.name || "Розетка " + r.relay_id)}</span>
      <button class="toggle ${r.state ? "on" : ""}" ${c.is_online ? "" : "disabled"}>
        ${r.state ? "Выключить" : "Включить"}</button>`;
    li.querySelector("button").onclick = guard(async () => {
      await api(`/api/relays/${r.id}/state`, "POST", { state: !r.state });
      await loadControllers();
    });
    ul.appendChild(li);
  }

  card.querySelector("[data-on]").onclick = guard(async () => {
    await api(`/api/controllers/${c.id}/all`, "POST", { state: true });
    toast("Все розетки контроллера включены", "success");
    await loadControllers();
  });
  card.querySelector("[data-off]").onclick = guard(async () => {
    await api(`/api/controllers/${c.id}/all`, "POST", { state: false });
    toast("Все розетки контроллера выключены", "success");
    await loadControllers();
  });

  if (isAdmin) {
    card.querySelector("[data-del]").onclick = async () => {
      const ok = await confirmAction({
        title: "Удалить контроллер?",
        text: `${c.name || c.ip} (${c.ip}) и все его розетки будут удалены из базы.` +
          (c.is_online ? " Устройство сейчас в сети — оно будет найдено заново при следующем сканировании." : ""),
        okText: "Да, удалить", cancelText: "Нет",
      });
      if (!ok) return;
      try {
        await api(`/api/controllers/${c.id}`, "DELETE");
        toast("Контроллер удалён", "success");
        await loadControllers();
      } catch (e) { toast(e.message, "error"); }
    };
  }
  return card;
}

async function initDashboard() {
  const me = await api("/api/auth/me");
  bindCommon(me);
  isAdmin = me.role === "admin";

  $("#refresh").onclick = guard(async () => {
    await api("/api/refresh", "POST");
    await loadControllers();
    toast("Статусы обновлены", "success");
  });
  $("#scan").onclick = guard(async () => {
    const r = await api("/api/scan", "POST");
    toast("Найдено контроллеров: " + r.found, "success");
    await loadControllers();
  });
  $("#all-on").onclick = guard(async () => {
    const r = await api("/api/relays/all", "POST", { state: true });
    toast(r.ok ? "Все розетки включены" : "Часть устройств недоступна: " + r.failed.join(", "), r.ok ? "success" : "error");
    await loadControllers();
  });
  $("#all-off").onclick = guard(async () => {
    const r = await api("/api/relays/all", "POST", { state: false });
    toast(r.ok ? "Все розетки выключены" : "Часть устройств недоступна: " + r.failed.join(", "), r.ok ? "success" : "error");
    await loadControllers();
  });
  await loadControllers();
  setInterval(guard(loadControllers), 5000);
}

/* ---------- Админка ---------- */
let usersCache = [];

async function loadUsers() {
  usersCache = await api("/api/users");
  usersCache.sort((a, b) => a.username.localeCompare(b.username, "ru"));
  renderUsers();
}

function renderUsers() {
  const q = ($("#user-search").value || "").trim().toLowerCase();
  const role = $("#role-filter").value;
  const list = usersCache.filter((u) =>
    (!q || u.username.toLowerCase().includes(q)) && (role === "all" || u.role === role)
  );
  const root = $("#users");
  root.innerHTML = "";
  if (!list.length) {
    root.innerHTML = '<div class="empty">Пользователи не найдены</div>';
    return;
  }
  for (const u of list) {
    const row = document.createElement("div");
    row.className = "user-row";
    const initials = u.username.slice(0, 2).toUpperCase();
    row.innerHTML = `
      <div class="user-main">
        <span class="avatar ${u.role === "admin" ? "admin" : ""}">${esc(initials)}</span>
        <div>
          <div class="user-name">${esc(u.username)}
            ${u.id === currentUser.id ? '<span class="you">вы</span>' : ""}
          </div>
          <div class="user-meta">ID ${u.id}</div>
        </div>
      </div>
      <div class="user-badges">
        <span class="chip ${u.role === "admin" ? "violet" : "cyan"}">${u.role === "admin" ? "админ" : "пользователь"}</span>
        <span class="chip ${u.is_active ? "green" : "red"}">${u.is_active ? "активен" : "отключён"}</span>
      </div>
      <div class="row-actions">
        <button class="icon-btn" data-edit title="Редактировать" aria-label="Редактировать пользователя">✏️</button>
        <button class="icon-btn danger" data-del title="Удалить" aria-label="Удалить пользователя">🗑</button>
      </div>`;
    row.querySelector("[data-edit]").onclick = () => openUserModal(u);
    row.querySelector("[data-del]").onclick = () => deleteUser(u);
    root.appendChild(row);
  }
}

async function openUserModal(user = null) {
  const isEdit = !!user;
  await openModal({
    title: isEdit ? "Редактировать пользователя" : "Новый пользователь",
    subtitle: isEdit ? `Учётная запись «${user.username}»` : "Создание учётной записи",
    okText: "Сохранить", cancelText: "Отменить",
    body: `
      <label class="field"><span>Логин</span>
        <input name="username" value="${esc(user ? user.username : "")}" required minlength="3" maxlength="64" autocomplete="off">
      </label>
      <label class="field"><span>${isEdit ? "Новый пароль" : "Пароль"}</span>
        <input name="password" type="password" ${isEdit ? "" : "required"} minlength="6" maxlength="72"
          placeholder="${isEdit ? "Оставьте пустым, чтобы не менять" : "Минимум 6 символов"}" autocomplete="new-password">
      </label>
      <label class="field"><span>Роль</span>
        <select name="role">
          <option value="user" ${!isEdit || user.role === "user" ? "selected" : ""}>Пользователь</option>
          <option value="admin" ${isEdit && user.role === "admin" ? "selected" : ""}>Администратор</option>
        </select>
      </label>
      <label class="switch-row">
        <input type="checkbox" name="is_active" ${!isEdit || user.is_active ? "checked" : ""}>
        <span>Аккаунт активен</span>
      </label>`,
    onSubmit: async (fd) => {
      const username = fd.get("username").trim();
      const password = fd.get("password");
      const role = fd.get("role");
      const is_active = fd.get("is_active") === "on";

      if (isEdit) {
        const payload = { username, role, is_active };
        if (password) payload.password = password;
        await api(`/api/users/${user.id}`, "PATCH", payload);
        toast("Пользователь обновлён", "success");
        if (user.id === currentUser.id) {
          currentUser = await api("/api/auth/me");
          if (currentUser.role !== "admin") { location.href = "/"; return true; }
        }
      } else {
        if (!password) throw new Error("Укажите пароль");
        await api("/api/users", "POST", { username, password, role });
        toast("Пользователь создан", "success");
      }
      await loadUsers();
      return true;
    },
  });
}

async function deleteUser(u) {
  const ok = await confirmAction({
    title: "Удалить пользователя?",
    text: `Удалить учётную запись «${u.username}»? Это действие нельзя отменить.`,
    okText: "Да, удалить", cancelText: "Нет",
  });
  if (!ok) return;
  try {
    await api(`/api/users/${u.id}`, "DELETE");
    toast("Пользователь удалён", "success");
    await loadUsers();
  } catch (e) { toast(e.message, "error"); }
}

async function initAdmin() {
  const me = await api("/api/auth/me");
  if (me.role !== "admin") { location.href = "/"; return; }
  bindCommon(me);
  $("#add-user").onclick = () => openUserModal(null);
  $("#user-search").oninput = renderUsers;
  $("#role-filter").onchange = renderUsers;
  await loadUsers();
}

/* ---------- Роутер страниц ---------- */
({ login: initLogin, dashboard: initDashboard, admin: initAdmin })[document.body.dataset.page]();