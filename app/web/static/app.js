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
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    let msg = "Ошибка " + res.status;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

const guard = (fn) => async (...args) => {
  try { await fn(...args); } catch (e) { alert(e.message); }
};

/* ---------- Логин ---------- */
function initLogin() {
  $("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api("/api/auth/login", "POST",
        { username: f.get("username"), password: f.get("password") });
      location.href = "/";
    } catch (err) { $("#error").textContent = err.message; }
  };
}

/* ---------- Дашборд ---------- */
async function loadControllers() {
  const list = await api("/api/controllers");
  const root = $("#controllers");
  root.innerHTML = "";
  if (!list.length) {
    root.innerHTML = '<p class="muted">Контроллеры не найдены. Дождитесь скана сети или нажмите «Сканировать сеть».</p>';
    return;
  }
  for (const c of list) {
    const card = document.createElement("section");
    card.className = "card" + (c.is_online ? "" : " offline");
    card.innerHTML = `
      <header>
        <h2>${esc(c.name || c.ip)}</h2>
        <span class="badge ${c.is_online ? "on" : "off"}">${c.is_online ? "online" : "offline"}</span>
        <span class="ip">${esc(c.ip)}</span>
        <button data-act="on">Включить все</button>
        <button data-act="off">Выключить все</button>
      </header>
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
    card.querySelector('[data-act="on"]').onclick = guard(async () => {
      await api(`/api/controllers/${c.id}/all`, "POST", { state: true });
      await loadControllers();
    });
    card.querySelector('[data-act="off"]').onclick = guard(async () => {
      await api(`/api/controllers/${c.id}/all`, "POST", { state: false });
      await loadControllers();
    });
    root.appendChild(card);
  }
}

async function initDashboard() {
  const me = await api("/api/auth/me");
  $("#whoami").textContent = me.username;
  if (me.role === "admin") {
    $("#admin-link").hidden = false;
    $("#scan").hidden = false;
  }
  $("#logout").onclick = guard(async () => {
    await api("/api/auth/logout", "POST");
    location.href = "/login";
  });
  $("#refresh").onclick = guard(async () => { await api("/api/refresh", "POST"); await loadControllers(); });
  $("#scan").onclick = guard(async () => {
    const r = await api("/api/scan", "POST");
    alert("Найдено контроллеров: " + r.found);
    await loadControllers();
  });
  $("#all-on").onclick = guard(async () => { await api("/api/relays/all", "POST", { state: true }); await loadControllers(); });
  $("#all-off").onclick = guard(async () => { await api("/api/relays/all", "POST", { state: false }); await loadControllers(); });
  await loadControllers();
  setInterval(guard(loadControllers), 5000);
}

/* ---------- Админка ---------- */
let usersCache = [];

async function loadUsers() {
  usersCache = await api("/api/users");
  const tbody = $("#users");
  tbody.innerHTML = "";
  for (const u of usersCache) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${u.id}</td><td>${esc(u.username)}</td><td>${u.role}</td>
      <td>${u.is_active ? "да" : "нет"}</td>
      <td><button data-act="edit">Изменить</button>
          <button data-act="del">Удалить</button></td>`;
    tr.querySelector('[data-act="edit"]').onclick = () => fillForm(u);
    tr.querySelector('[data-act="del"]').onclick = guard(async () => {
      if (!confirm(`Удалить пользователя ${u.username}?`)) return;
      await api(`/api/users/${u.id}`, "DELETE");
      await loadUsers();
    });
    tbody.appendChild(tr);
  }
}

function fillForm(u) {
  const f = $("#user-form");
  f.id.value = u ? u.id : "";
  f.username.value = u ? u.username : "";
  f.username.disabled = !!u;             // логин не меняем
  f.password.value = "";
  f.password.required = !u;
  f.role.value = u ? u.role : "user";
  f.is_active.checked = u ? u.is_active : true;
  $("#form-title").textContent = u ? "Редактирование: " + u.username : "Новый пользователь";
  $("#form-error").textContent = "";
}

async function initAdmin() {
  const me = await api("/api/auth/me");
  if (me.role !== "admin") { location.href = "/"; return; }
  $("#logout").onclick = guard(async () => {
    await api("/api/auth/logout", "POST");
    location.href = "/login";
  });
  $("#reset-form").onclick = () => fillForm(null);
  $("#user-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target;
    const id = f.id.value;
    try {
      if (id) {
        const body = { role: f.role.value, is_active: f.is_active.checked };
        if (f.password.value) body.password = f.password.value;
        await api(`/api/users/${id}`, "PATCH", body);
      } else {
        await api("/api/users", "POST",
          { username: f.username.value, password: f.password.value, role: f.role.value });
      }
      fillForm(null);
      await loadUsers();
    } catch (err) { $("#form-error").textContent = err.message; }
  };
  fillForm(null);
  await loadUsers();
}

/* ---------- Роутер страниц ---------- */
({ login: initLogin, dashboard: initDashboard, admin: initAdmin })[document.body.dataset.page]();