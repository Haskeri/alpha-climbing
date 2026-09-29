(() => {
  const API = window.ALPHA_API_URL;
  const ROLE_NAMES = { admin: "Администратор", leader: "Руководитель группы", climber: "Альпинист" };
  const STATUS_NAMES = { completed: "Восхождение совершено", active: "На маршруте", planned: "Запланировано" };
  const TITLES = { peaks: "Вершины", groups: "Группы", climbers: "Альпинисты", profile: "Профиль" };

  const state = {
    token: localStorage.getItem("alpha_token"),
    user: JSON.parse(localStorage.getItem("alpha_user") || "null"),
    tab: "peaks",
    peaks: [],
    climbers: [],
  };

  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
  const canEdit = () => state.user && ["leader", "admin"].includes(state.user.role);

  async function request(path, options = {}) {
    const headers = { "Content-Type": "application/json" };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    const res = await fetch(API + path, { ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Ошибка ${res.status}`);
    return data;
  }

  function toast(text, isError = false) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.add("hidden"), 2600);
  }

  async function checkServer() {
    try {
      const h = await request("/health");
      $("#server-status").classList.add("online");
      $("#server-status").title = `Сервер ${h.host} · БД ${h.database} · v${h.version}`;
    } catch {
      $("#server-status").classList.remove("online");
    }
  }

  // ---------- Авторизация ----------

  function setSession(token, user) {
    state.token = token;
    state.user = user;
    if (token) {
      localStorage.setItem("alpha_token", token);
      localStorage.setItem("alpha_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("alpha_token");
      localStorage.removeItem("alpha_user");
    }
  }

  function showMain() {
    $("#screen-auth").classList.add("hidden");
    $("#screen-main").classList.remove("hidden");
    $("#tabbar").classList.remove("hidden");
    openTab(state.tab);
  }

  function showAuth() {
    $("#screen-main").classList.add("hidden");
    $("#tabbar").classList.add("hidden");
    $("#screen-auth").classList.remove("hidden");
  }

  document.querySelectorAll("[data-auth-tab]").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-auth-tab]").forEach((b) => b.classList.toggle("active", b === btn));
      $("#form-login").classList.toggle("hidden", btn.dataset.authTab !== "login");
      $("#form-register").classList.toggle("hidden", btn.dataset.authTab !== "register");
    })
  );

  $("#form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.target));
    try {
      const data = await request("/auth/login", { method: "POST", body: JSON.stringify(form) });
      setSession(data.token, data.user);
      toast(`Здравствуйте, ${data.user.full_name.split(" ")[1] || data.user.login}!`);
      e.target.reset();
      showMain();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $("#form-register").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.target));
    try {
      const data = await request("/auth/register", { method: "POST", body: JSON.stringify(form) });
      toast(data.message);
      e.target.reset();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $("#btn-guest").addEventListener("click", () => {
    setSession(null, null);
    showMain();
  });

  // ---------- Навигация ----------

  document.querySelectorAll("[data-tab]").forEach((btn) => btn.addEventListener("click", () => openTab(btn.dataset.tab)));

  async function openTab(tab) {
    state.tab = tab;
    document.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    $("#section-title").textContent = TITLES[tab];
    $("#btn-add").classList.toggle("hidden", !(canEdit() && tab !== "profile"));
    $("#list").innerHTML = '<div class="empty">Загрузка…</div>';
    try {
      await RENDER[tab]();
    } catch (err) {
      $("#list").innerHTML = `<div class="empty">Не удалось загрузить данные: ${esc(err.message)}</div>`;
    }
  }

  const RENDER = {
    async peaks() {
      state.peaks = await request("/peaks");
      $("#list").innerHTML = state.peaks.length
        ? state.peaks
            .map(
              (p) => `
          <div class="card item">
            <div class="item-top"><div class="item-title">${esc(p.name)}</div><div class="height">${p.height.toLocaleString("ru-RU")} м</div></div>
            <div class="item-meta">${esc(p.country)} · групп: ${p.groups_count}</div>
            <div class="row">
              <span class="badge ${p.has_ascent ? "completed" : "planned"}">${p.has_ascent ? "Есть восхождения" : "Восхождений нет"}</span>
              ${canEdit() && !p.has_ascent ? `<button class="btn small" data-edit-peak="${p.id}">Изменить</button>` : ""}
            </div>
          </div>`
            )
            .join("")
        : '<div class="empty">Вершин пока нет</div>';
      document.querySelectorAll("[data-edit-peak]").forEach((b) =>
        b.addEventListener("click", () => peakForm(state.peaks.find((p) => p.id === Number(b.dataset.editPeak))))
      );
    },

    async groups() {
      const groups = await request("/groups");
      $("#list").innerHTML = groups.length
        ? groups
            .map(
              (g) => `
          <div class="card item">
            <div class="item-top"><div class="item-title">${esc(g.name)}</div><span class="badge ${g.status}">${STATUS_NAMES[g.status]}</span></div>
            <div class="item-meta">▲ ${esc(g.peak.name)} (${g.peak.height} м) · ${fmtDate(g.start_date)} — ${fmtDate(g.end_date)}</div>
            <div class="item-meta">Руководитель: ${esc(g.leader || "—")}</div>
            <div class="chips">${g.members.map((m) => `<span class="chip">${esc(m.full_name.split(" ").slice(0, 2).join(" "))}</span>`).join("") || '<span class="item-meta">Участников нет</span>'}</div>
            ${canEdit() ? `<div class="row"><button class="btn small" data-add-member="${g.id}">+ Участник</button></div>` : ""}
          </div>`
            )
            .join("")
        : '<div class="empty">Групп пока нет</div>';
      document.querySelectorAll("[data-add-member]").forEach((b) =>
        b.addEventListener("click", () => memberForm(Number(b.dataset.addMember)))
      );
    },

    async climbers() {
      state.climbers = await request("/climbers");
      $("#list").innerHTML = state.climbers.length
        ? state.climbers
            .map(
              (c) => `
          <div class="card item">
            <div class="item-top"><div class="item-title">${esc(c.full_name)}</div><span class="badge">${esc(c.rank)}</span></div>
            <div class="item-meta">${c.birth_year ? `${c.birth_year} г. р. · ` : ""}восхождений: ${c.ascents}</div>
          </div>`
            )
            .join("")
        : '<div class="empty">Альпинистов пока нет</div>';
    },

    async profile() {
      const stats = await request("/stats");
      const health = await request("/health");
      let html = state.user
        ? `<div class="card item">
             <div class="item-title">${esc(state.user.full_name)}</div>
             <div class="item-meta">Логин: ${esc(state.user.login)}</div>
             <div class="row"><span class="badge completed">${ROLE_NAMES[state.user.role]}</span></div>
           </div>`
        : `<div class="card item"><div class="item-title">Гостевой режим</div>
             <div class="item-meta">Доступен только просмотр информации</div></div>`;
      html += `<div class="stats">
          <div class="stat"><b>${stats.peaks}</b><span>вершин</span></div>
          <div class="stat"><b>${stats.groups}</b><span>групп</span></div>
          <div class="stat"><b>${stats.climbers}</b><span>альпинистов</span></div>
          <div class="stat"><b>${stats.users}</b><span>пользователей</span></div>
        </div>
        <div class="card item" style="margin-top:10px">
          <div class="item-meta">Сервер: ${esc(health.host)} · БД: ${esc(health.database)} · API v${esc(health.version)}</div>
        </div>`;
      if (state.user && state.user.role === "admin") {
        const pending = await request("/admin/requests");
        html += `<h3>Заявки на регистрацию</h3>` +
          (pending.length
            ? pending.map((u) => `
              <div class="card item">
                <div class="item-title">${esc(u.full_name)}</div>
                <div class="item-meta">Логин: ${esc(u.login)}</div>
                <div class="row">
                  <button class="btn small" data-approve="${u.id}" data-role="climber">Альпинист</button>
                  <button class="btn small" data-approve="${u.id}" data-role="leader">Руководитель</button>
                </div>
              </div>`).join("")
            : '<div class="empty">Новых заявок нет</div>');
      }
      html += `<div style="margin-top:14px"><button class="btn danger" id="btn-logout" style="width:100%">${state.user ? "Выйти" : "Войти в систему"}</button></div>`;
      $("#list").innerHTML = html;
      document.querySelectorAll("[data-approve]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            await request(`/admin/requests/${b.dataset.approve}/approve`, { method: "POST", body: JSON.stringify({ role: b.dataset.role }) });
            toast("Заявка подтверждена");
            openTab("profile");
          } catch (err) {
            toast(err.message, true);
          }
        })
      );
      $("#btn-logout").addEventListener("click", () => {
        setSession(null, null);
        showAuth();
      });
    },
  };

  // ---------- Формы добавления ----------

  function openModal(title, fieldsHtml, onSubmit) {
    $("#modal-title").textContent = title;
    $("#modal-form").innerHTML = fieldsHtml + '<button class="btn primary" type="submit">Сохранить</button>';
    $("#modal").classList.remove("hidden");
    $("#modal-form").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await onSubmit(Object.fromEntries(new FormData(e.target)));
        closeModal();
        openTab(state.tab);
      } catch (err) {
        toast(err.message, true);
      }
    };
  }

  function closeModal() {
    $("#modal").classList.add("hidden");
  }

  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => e.target.id === "modal" && closeModal());

  function peakForm(peak) {
    openModal(
      peak ? "Изменить вершину" : "Новая вершина",
      `<label>Название<input name="name" required value="${esc(peak?.name)}"></label>
       <label>Высота, м<input name="height" type="number" min="100" max="8849" required value="${peak?.height ?? ""}"></label>
       <label>Страна<input name="country" required value="${esc(peak?.country)}"></label>`,
      async (data) => {
        await request(peak ? `/peaks/${peak.id}` : "/peaks", { method: peak ? "PUT" : "POST", body: JSON.stringify(data) });
        toast(peak ? "Вершина изменена" : `Вершина «${data.name}» добавлена`);
      }
    );
  }

  async function groupForm() {
    const peaks = state.peaks.length ? state.peaks : await request("/peaks");
    openModal(
      "Новая группа",
      `<label>Название группы<input name="name" required></label>
       <label>Вершина<select name="peak_id">${peaks.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.height} м)</option>`).join("")}</select></label>
       <label>Дата начала<input name="start_date" type="date" required></label>
       <label>Дата окончания<input name="end_date" type="date" required></label>`,
      async (data) => {
        data.peak_id = Number(data.peak_id);
        await request("/groups", { method: "POST", body: JSON.stringify(data) });
        toast(`Группа «${data.name}» создана`);
      }
    );
  }

  async function memberForm(groupId) {
    const climbers = await request("/climbers");
    openModal(
      "Добавить участника",
      `<label>Альпинист<select name="climber_id">${climbers.map((c) => `<option value="${c.id}">${esc(c.full_name)} — ${esc(c.rank)}</option>`).join("")}</select></label>`,
      async (data) => {
        await request(`/groups/${groupId}/members`, { method: "POST", body: JSON.stringify({ climber_id: Number(data.climber_id) }) });
        toast("Участник добавлен в группу");
      }
    );
  }

  function climberForm() {
    openModal(
      "Новый альпинист",
      `<label>ФИО<input name="full_name" required></label>
       <label>Год рождения<input name="birth_year" type="number" min="1930" max="2015"></label>
       <label>Спортивный разряд<select name="rank">
         ${["без разряда", "3 разряд", "2 разряд", "1 разряд", "КМС", "МС"].map((r) => `<option>${r}</option>`).join("")}
       </select></label>`,
      async (data) => {
        await request("/climbers", { method: "POST", body: JSON.stringify(data) });
        toast(`Альпинист ${data.full_name} добавлен`);
      }
    );
  }

  $("#btn-add").addEventListener("click", () => ({ peaks: () => peakForm(null), groups: groupForm, climbers: climberForm }[state.tab]?.()));

  // ---------- Запуск ----------

  checkServer();
  setInterval(checkServer, 15000);
  if (state.token) {
    request("/auth/me")
      .then((user) => {
        state.user = user;
        showMain();
      })
      .catch(() => {
        setSession(null, null);
        showAuth();
      });
  } else {
    showAuth();
  }
})();
