(() => {
  const $ = (id) => document.getElementById(id);
  const splash = $("splash");
  const cockpit = $("cockpit");
  const chat = $("chat");
  const form = $("form");
  const input = $("input");
  const send = $("send");

  let busy = false;
  let statusCache = {};

  async function api(path, body) {
    const res = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.message || `HTTP ${res.status}`);
    return data;
  }

  function addMsg(role, text) {
    const el = document.createElement("article");
    el.className = `msg ${role}`;
    if (role === "system") {
      el.textContent = text;
    } else {
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = role === "user" ? "Sen" : "REIS AI";
      el.appendChild(who);
      el.appendChild(document.createTextNode(text || ""));
    }
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  function setView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    const titles = { chat: "Sohbet", evolve: "Evolution", systems: "Sistemler", ops: "Operasyon" };
    $("viewTitle").textContent = titles[name] || name;
    $("eyebrow").textContent = "Command Center · ULTRA";
  }

  function renderModels(models) {
    const strip = $("modelStrip");
    strip.innerHTML = "";
    Object.entries(models || {}).forEach(([k, v]) => {
      if (!v) return;
      const c = document.createElement("span");
      c.className = "chip";
      c.textContent = `${k} · ${v}`;
      strip.appendChild(c);
    });
  }

  function renderSystems(systems) {
    const grid = $("systemsGrid");
    grid.innerHTML = "";
    const entries = Object.entries(systems || {});
    if (!entries.length) {
      grid.innerHTML = '<div class="muted">Sistem verisi yok — Boot çalıştır.</div>';
      return;
    }
    entries.forEach(([name, info]) => {
      const el = document.createElement("div");
      el.className = `sys ${info.ok ? "ok" : "bad"}`;
      el.innerHTML = `<div class="n">${info.ok ? "●" : "○"} ${name}</div><div class="d">${info.detail || (info.ok ? "online" : "offline")}</div>`;
      grid.appendChild(el);
    });
  }

  function renderKit(kit) {
    const ul = $("kitList");
    ul.innerHTML = "";
    (kit || []).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    });
  }

  function renderList(el, rows, empty) {
    if (!rows || !rows.length) {
      el.textContent = empty;
      return;
    }
    el.textContent = rows.join("\n");
  }

  async function refreshStatus() {
    try {
      const st = await api("/api/status");
      statusCache = st;
      $("liveDot").classList.toggle("on", !!st.ollama_ok);
      $("liveLabel").textContent = st.ollama_ok ? "çevrimiçi" : "sınırlı";
      $("sysPill").textContent = `${st.evolution_active || 0}/${st.evolution_total || 0} sistem · v${st.version || "ultra"}`;
      $("mCpu").textContent = st.cpu != null ? `${st.cpu}%` : "—";
      $("mRam").textContent = st.ram != null ? `${st.ram}%` : "—";
      $("mBoot").textContent = st.startup_s != null ? `${st.startup_s}s` : "—";
      $("mErr").textContent = st.error_rate != null ? String(st.error_rate) : "—";
      renderModels(st.models);
      renderSystems(st.systems);
      renderKit(st.kit);
      $("tgStatus").textContent = st.telegram_configured
        ? "Token tanımlı — bot hazır / arka planda çalışabilir"
        : "Token yok — .env içine TELEGRAM_BOT_TOKEN ekle";
      renderList($("projectList"), st.projects, "Kayıtlı proje yok");
      renderList($("taskList"), st.tasks, "Görev yok");
      if (st.diagnostics) {
        $("dFiles").textContent = st.diagnostics.python_files ?? "—";
        $("dProblems").textContent = st.diagnostics.problems ?? "—";
        $("dGaps").textContent = st.diagnostics.test_gaps ?? "—";
        $("dSec").textContent = st.diagnostics.security ?? "—";
      }
    } catch (e) {
      $("liveDot").classList.remove("on");
      $("liveLabel").textContent = "bağlantı yok";
      $("sysPill").textContent = String(e.message || e);
    }
  }

  async function sendText(text) {
    const msg = (text || "").trim();
    if (!msg || busy) return;
    busy = true;
    send.disabled = true;
    setView("chat");
    addMsg("user", msg);
    input.value = "";
    autoSize();
    const thinking = addMsg("assistant", "…");
    try {
      const data = await api("/api/handle", { message: msg });
      thinking.remove();
      addMsg("assistant", data.message || "(boş)");
      refreshStatus();
    } catch (e) {
      thinking.remove();
      addMsg("assistant", `Hata: ${e.message || e}`);
    } finally {
      busy = false;
      send.disabled = false;
      input.focus();
    }
  }

  function autoSize() {
    input.style.height = "auto";
    input.style.height = Math.min(150, Math.max(56, input.scrollHeight)) + "px";
  }

  $("enterBtn").addEventListener("click", () => {
    splash.classList.add("out");
    setTimeout(() => {
      splash.classList.add("hidden");
      cockpit.classList.remove("hidden");
      input.focus();
    }, 400);
  });

  document.querySelectorAll(".nav-btn").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  document.querySelectorAll(".qbtn").forEach((b) => b.addEventListener("click", () => sendText(b.dataset.cmd)));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendText(input.value);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendText(input.value);
    }
  });
  input.addEventListener("input", autoSize);
  $("clearChat").addEventListener("click", () => {
    chat.innerHTML = "";
    addMsg("system", "Sohbet temizlendi. REIS AI ULTRA hazır.");
  });

  $("runEvolve").addEventListener("click", async () => {
    $("evolveLog").textContent = "Evolution çalışıyor…";
    try {
      const data = await api("/api/evolve", {});
      $("evolveLog").textContent = data.message || JSON.stringify(data, null, 2);
      refreshStatus();
    } catch (e) {
      $("evolveLog").textContent = String(e.message || e);
    }
  });

  $("runDiagnose").addEventListener("click", async () => {
    try {
      const data = await api("/api/diagnose");
      $("dFiles").textContent = data.python_files ?? "—";
      $("dProblems").textContent = data.problems ?? "—";
      $("dGaps").textContent = data.test_gaps ?? "—";
      $("dSec").textContent = data.security ?? "—";
      $("evolveLog").textContent = (data.recommendations || []).join("\n") || "OK";
    } catch (e) {
      $("evolveLog").textContent = String(e.message || e);
    }
  });

  addMsg("system", "REIS AI ULTRA konsolu hazır. Soldan Full Evolve veya aşağıya hedef yaz.");
  refreshStatus();
  setInterval(refreshStatus, 12000);
})();
