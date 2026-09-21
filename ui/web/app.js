(() => {
  const chat = document.getElementById("chat");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  const sysPill = document.getElementById("sysPill");
  const modelLine = document.getElementById("modelLine");
  const liveDot = document.getElementById("liveDot");
  const liveLabel = document.getElementById("liveLabel");
  const headline = document.getElementById("headline");

  let busy = false;

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

  async function api(path, body) {
    const res = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  async function refreshStatus() {
    try {
      const st = await api("/api/status");
      liveDot.classList.add("on");
      liveLabel.textContent = st.ollama_ok ? "çevrimiçi" : "sınırlı";
      const a = st.evolution_active || 0;
      const t = st.evolution_total || 0;
      sysPill.textContent = t ? `${a}/${t} sistem aktif` : "hazır";
      const m = st.models || {};
      modelLine.textContent = [
        m.FAST && `FAST ${m.FAST}`,
        m.CODING && `CODE ${m.CODING}`,
        m.ANALYSIS && `ANALIZ ${m.ANALYSIS}`,
      ]
        .filter(Boolean)
        .join(" · ");
      if (st.brand) headline.textContent = st.brand;
    } catch (e) {
      liveDot.classList.remove("on");
      liveLabel.textContent = "bağlantı yok";
      sysPill.textContent = "offline";
      modelLine.textContent = String(e.message || e);
    }
  }

  async function sendText(text) {
    const msg = (text || "").trim();
    if (!msg || busy) return;
    busy = true;
    send.disabled = true;
    addMsg("user", msg);
    input.value = "";
    autoSize();
    const thinking = addMsg("assistant", "…");
    try {
      const data = await api("/api/handle", { message: msg });
      thinking.remove();
      addMsg("assistant", data.message || "(boş yanıt)");
      if (data.kind === "evolution") refreshStatus();
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
    input.style.height = Math.min(140, Math.max(52, input.scrollHeight)) + "px";
  }

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

  document.querySelectorAll(".act").forEach((btn) => {
    btn.addEventListener("click", () => sendText(btn.dataset.cmd || ""));
  });

  addMsg(
    "system",
    "REIS AI hazır. Soldan Evolve ile kendini geliştirebilir veya aşağıya hedef yazabilirsin."
  );
  refreshStatus();
  setInterval(refreshStatus, 15000);
})();
