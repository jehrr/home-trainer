"use strict";

const $ = (id) => document.getElementById(id);
let currentId = null;
let busy = false;

const SUGGESTIONS = [
  "Что у меня сегодня по плану и готов ли я к нему?",
  "Разбери последнюю тренировку",
  "Как я восстановился за неделю?",
  "Завтра еду утром — посмотри погоду и скажи, что надеть",
];

// ── Утилиты ─────────────────────────────────────────────

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function inline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}

// Небольшой разбор markdown: заголовки, списки, таблицы, абзацы
function renderMarkdown(text) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) { out.push(`<h${h[1].length > 2 ? 4 : 3}>${inline(h[2])}</h${h[1].length > 2 ? 4 : 3}>`); i++; continue; }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      let html = "<table><thead><tr>" + cells(line).map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        html += "<tr>" + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>";
        i++;
      }
      out.push(html + "</tbody></table>");
      continue;
    }
    if (/^\s*([-*•]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*•]|\d+[.)])\s+/, ""));
        i++;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>` + items.map((t) => `<li>${inline(t)}</li>`).join("") + `</${tag}>`);
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\s*([-*•]|\d+[.)])\s+|\s*\|)/.test(lines[i])) {
      para.push(lines[i]); i++;
    }
    if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`);
    else i++;
  }
  return out.join("");
}

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

function scrollDown() { const m = $("messages"); m.scrollTop = m.scrollHeight; }

// ── Сводка на сегодня ───────────────────────────────────

function setGauge(id, value, cls) {
  const el = $(id);
  el.textContent = value ?? "—";
  el.className = "g-val" + (cls ? " " + cls : "");
}

async function loadToday(refresh = false) {
  try {
    const t = await api("/api/today" + (refresh ? "?refresh=1" : ""));
    $("plan-line").textContent = t.plan;
    if (t.error) { $("today-note").textContent = t.error; return; }
    const d = t.latest || {};
    let hrvCls = "";
    if (d.hrv && t.hrv_avg) {
      const diff = d.hrv / t.hrv_avg - 1;
      hrvCls = diff <= -0.1 ? "bad" : diff < -0.03 ? "warn" : "good";
    }
    setGauge("g-hrv", d.hrv != null ? Math.round(d.hrv) : null, hrvCls);
    setGauge("g-sleep", d.sleep_h, d.sleep_h ? (d.sleep_h < 6 ? "bad" : d.sleep_h < 7 ? "warn" : "good") : "");
    setGauge("g-rhr", d.resting_hr != null ? Math.round(d.resting_hr) : null);
    setGauge("g-form", d.form_tsb != null ? Math.round(d.form_tsb) : null,
      d.form_tsb != null ? (d.form_tsb < -25 ? "bad" : d.form_tsb < -10 ? "warn" : "good") : "");
    const trend = (t.hrv_trend || []).filter((v) => v != null);
    const max = Math.max(...trend, 1), min = Math.min(...trend, max);
    const h = (v) => (max === min ? 70 : 25 + Math.round(((v - min) / (max - min)) * 75));
    $("spark").innerHTML = trend.map((v) => `<span style="height:${h(v)}%" title="HRV ${Math.round(v)}"></span>`).join("");
    $("today-note").textContent = d.date ? `Данные за ${d.date}${t.hrv_avg ? `, средний HRV за неделю ${t.hrv_avg}` : ""}` : "Нет данных восстановления";
  } catch (e) {
    $("today-note").textContent = "Не удалось загрузить данные восстановления";
  }
}

// ── Диалоги ─────────────────────────────────────────────

async function loadConversations() {
  const list = await api("/api/conversations");
  const nav = $("convs");
  nav.innerHTML = "";
  list.forEach((c) => {
    const row = document.createElement("div");
    row.className = "conv" + (c.id === currentId ? " active" : "");
    const name = document.createElement("button");
    name.className = "conv-name";
    name.textContent = c.title;
    name.onclick = () => openConversation(c.id);
    const del = document.createElement("button");
    del.className = "conv-del";
    del.textContent = "Удалить";
    del.setAttribute("aria-label", `Удалить диалог «${c.title}»`);
    del.onclick = async () => {
      if (!confirm(`Удалить диалог «${c.title}»?`)) return;
      await api(`/api/conversations/${c.id}`, { method: "DELETE" });
      if (c.id === currentId) currentId = null;
      await loadConversations();
      if (!currentId) showEmpty();
    };
    row.append(name, del);
    nav.append(row);
  });
  return list;
}

function showEmpty() {
  $("conv-title").textContent = "Новый диалог";
  $("messages").innerHTML =
    `<div class="empty"><h2>О чём поговорим?</h2>
     <p>Тренер сам посмотрит тренировки, восстановление, календарь и погоду, когда это нужно для ответа.</p>
     <div class="suggestions">${SUGGESTIONS.map((s) => `<button class="suggestion">${esc(s)}</button>`).join("")}</div></div>`;
  document.querySelectorAll(".suggestion").forEach((b) => (b.onclick = () => send(b.textContent)));
}

async function openConversation(id) {
  currentId = id;
  closeSide();
  const conv = await api(`/api/conversations/${id}`);
  $("conv-title").textContent = conv.title;
  const box = $("messages");
  box.innerHTML = "";
  if (!conv.messages.length) { showEmpty(); }
  conv.messages.forEach((m) => {
    if (m.role === "user") addUser(m.text);
    else {
      const el = addAssistant();
      m.tools.forEach((t) => addToolRow(el, t, "ok"));
      el.querySelector(".body").innerHTML = renderMarkdown(m.text || "");
    }
  });
  if (conv.running && !busy) showPending(id);
  else if (conv.needs_answer && !busy) showRetry();
  scrollDown();
  loadConversations();
  return conv;
}

function addUser(text) {
  const empty = document.querySelector(".empty");
  if (empty) empty.remove();
  const el = document.createElement("div");
  el.className = "msg user";
  el.textContent = text;
  $("messages").append(el);
  return el;
}

function addAssistant() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<div class="tool-log"></div><div class="body"></div>`;
  $("messages").append(el);
  return el;
}

function addToolRow(el, label, state) {
  const row = document.createElement("div");
  row.className = `tool-row ${state}`;
  row.textContent = label;
  el.querySelector(".tool-log").append(row);
  return row;
}

// ── Отправка и стриминг ─────────────────────────────────

async function send(text) {
  text = (text || "").trim();
  if (!text || busy) return;
  if (!currentId) {
    const { id } = await api("/api/conversations", { method: "POST" });
    currentId = id;
  }
  addUser(text);
  await streamAnswer(`/api/conversations/${currentId}/chat`, { message: text });
}

async function retryAnswer() {
  if (busy || !currentId) return;
  document.querySelectorAll(".retry-box").forEach((el) => el.remove());
  await streamAnswer(`/api/conversations/${currentId}/retry`, {});
}

function showPending(id) {
  const box = document.createElement("div");
  box.className = "msg assistant retry-box";
  box.innerHTML = `<p class="retry-text"><span class="typing">Тренер ещё готовит ответ…</span></p>`;
  $("messages").append(box);
  // Перечитываем диалог каждые 3 секунды, пока ответ не будет готов
  setTimeout(() => { if (currentId === id && !busy) openConversation(id); }, 3000);
}

function showRetry() {
  const box = document.createElement("div");
  box.className = "msg assistant retry-box";
  box.innerHTML = `<p class="retry-text">Ответ на этот вопрос не пришёл.</p><button class="ghost-dark-btn">Повторить</button>`;
  box.querySelector("button").onclick = retryAnswer;
  $("messages").append(box);
  scrollDown();
}

async function streamAnswer(url, payload) {
  busy = true;
  $("send").disabled = true;
  const convAtStart = currentId;
  const el = addAssistant();
  const body = el.querySelector(".body");
  body.innerHTML = `<span class="typing">Думаю…</span>`;
  scrollDown();

  let answer = "";
  let failed = false;
  let pendingRow = null;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        if (!chunk.startsWith("data: ")) continue;
        const ev = JSON.parse(chunk.slice(6));
        if (currentId !== convAtStart) continue; // пользователь ушёл в другой диалог — ответ всё равно сохранится
        if (ev.type === "text") {
          answer += ev.delta;
          body.innerHTML = renderMarkdown(answer);
        } else if (ev.type === "tool") {
          if (!answer) body.innerHTML = "";
          else answer += "\n\n";
          pendingRow = addToolRow(el, ev.label, "running");
        } else if (ev.type === "tool_done" && pendingRow) {
          pendingRow.className = "tool-row " + (ev.ok ? "ok" : "fail");
          if (!ev.ok && ev.error) pendingRow.title = ev.error;
          pendingRow = null;
          if (!answer) body.innerHTML = `<span class="typing">Думаю…</span>`;
        } else if (ev.type === "error") {
          failed = true;
          const err = document.createElement("div");
          err.className = "msg error";
          err.textContent = ev.message;
          el.append(err);
        }
        scrollDown();
      }
    }
  } catch (e) {
    failed = true;
    body.innerHTML = `<div class="msg error">Ответ не получен: ${esc(e.message)}</div>`;
  } finally {
    if (!answer && body.querySelector(".typing")) body.innerHTML = "";
    busy = false;
    $("send").disabled = false;
    if (currentId === convAtStart && (failed || !answer.trim())) showRetry();
    $("input").focus();
    loadLastRide();
    loadConversations().then((list) => {
      const c = list.find((x) => x.id === currentId);
      if (c) $("conv-title").textContent = c.title;
    });
  }
}

// ── Память тренера ──────────────────────────────────────

let memoryDirty = false;

async function openMemory() {
  const m = await api("/api/memory");
  const b = $("memory-body");
  memoryDirty = false;
  const profileRows = Object.entries(m.profile_labels).map(([key, label]) =>
    `<label class="prof-row"><span>${esc(label)}</span><input data-key="${key}" data-orig="${esc(m.profile[key] || "")}" value="${esc(m.profile[key] || "")}"${key === "plan_start_date" ? ' placeholder="2026-05-25"' : ""}></label>`).join("");
  const notes = m.notes.length
    ? m.notes.map((n) => `<div class="mem-item"><span>${esc(n.text)}<small>${esc(n.created_at.slice(0, 10))}</small></span><button class="mem-del" data-note="${n.id}">Удалить</button></div>`).join("")
    : `<p class="mem-hint">Пока пусто. Тренер добавляет сюда важные факты сам, можно дописать и вручную.</p>`;
  const places = `<p class="mem-hint">${m.places.length ? "Сохранено мест: " + m.places.length + ". " : ""}Места настраиваются в меню «Погода и места».</p>`;
  b.innerHTML = `<h3>План</h3><p class="mem-hint">${esc(m.plan)}</p>
    <h3>Профиль</h3>
    <form id="profile-form">${profileRows}
      <div class="form-actions"><button type="submit" class="primary-btn" id="profile-save" disabled>Сохранить</button><span class="save-msg" id="profile-msg"></span></div>
    </form>
    <h3>Заметки</h3>${notes}
    <form class="note-add" id="note-form"><input id="note-input" placeholder="Например: болит левое колено после длинных подъёмов"><button type="submit" class="ghost-dark-btn">Добавить</button></form>
    <h3>Места тренировок</h3>${places}`;

  const form = $("profile-form");
  const inputs = [...form.querySelectorAll("input[data-key]")];
  const refreshDirty = () => {
    memoryDirty = inputs.some((i) => i.value.trim() !== i.dataset.orig);
    $("profile-save").disabled = !memoryDirty;
    if (memoryDirty) $("profile-msg").textContent = "";
  };
  inputs.forEach((i) => (i.oninput = refreshDirty));
  form.onsubmit = async (e) => {
    e.preventDefault();
    const changed = inputs.filter((i) => i.value.trim() !== i.dataset.orig);
    if (!changed.length) return;
    $("profile-save").disabled = true;
    try {
      for (const i of changed) {
        await api("/api/profile", { method: "PUT", body: JSON.stringify({ key: i.dataset.key, value: i.value.trim() }) });
        i.dataset.orig = i.value.trim();
      }
      memoryDirty = false;
      $("profile-msg").textContent = "Сохранено";
      $("profile-msg").className = "save-msg ok";
      loadToday(true);
    } catch (err) {
      $("profile-msg").textContent = "Не сохранилось: " + err.message;
      $("profile-msg").className = "save-msg bad";
      refreshDirty();
    }
  };

  $("note-form").onsubmit = async (e) => {
    e.preventDefault();
    const text = $("note-input").value.trim();
    if (!text) return;
    await api("/api/notes", { method: "POST", body: JSON.stringify({ text }) });
    openMemory();
  };
  b.querySelectorAll("[data-note]").forEach((btn) => (btn.onclick = async () => {
    await api(`/api/notes/${btn.dataset.note}`, { method: "DELETE" }); openMemory();
  }));
  $("memory").hidden = false;
  $("memory-backdrop").hidden = false;
}

function closeMemory() {
  if ($("memory").hidden) return;
  if (memoryDirty && !confirm("Изменения в профиле не сохранены. Закрыть без сохранения?")) return;
  memoryDirty = false;
  $("memory").hidden = true;
  syncBackdrop();
}
function closeSide() { $("side").classList.remove("open"); }


// ── Погода и места ──────────────────────────────────────

let placesCache = [];

function parseCoord(v) {
  return parseFloat(String(v).trim().replace(",", "."));
}

async function renderPlaces(selectName) {
  placesCache = await api("/api/places");
  const list = $("places-list");
  list.innerHTML = placesCache.length
    ? placesCache.map((p) => `<div class="mem-item"><span>${esc(p.name)}<small>${p.latitude}, ${p.longitude}${p.note ? ". " + esc(p.note) : ""}</small></span>
        <span class="place-actions"><button class="mem-del" data-edit="${esc(p.name)}">Изменить</button><button class="mem-del" data-del="${esc(p.name)}">Удалить</button></span></div>`).join("")
    : `<p class="mem-hint">Пока нет сохранённых мест. Добавь первое ниже.</p>`;
  list.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm(`Удалить место «${b.dataset.del}»?`)) return;
    await api(`/api/places/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" });
    renderPlaces();
  }));
  list.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => {
    const p = placesCache.find((x) => x.name === b.dataset.edit);
    $("pl-name").value = p.name; $("pl-lat").value = p.latitude; $("pl-lon").value = p.longitude; $("pl-note").value = p.note || "";
    $("pl-name").focus();
  }));

  const sel = $("fc-place");
  const prev = selectName || sel.value;
  sel.innerHTML = placesCache.length
    ? placesCache.map((p) => `<option value="${esc(p.name)}">${esc(p.name)}</option>`).join("")
    : `<option value="">Сначала добавь место ниже</option>`;
  if (prev && placesCache.some((p) => p.name === prev)) sel.value = prev;
  $("fc-go").disabled = !placesCache.length;
}

function windFlagText(g) { return g >= 45 ? "опасные порывы" : "сильный ветер"; }

function renderForecast(fc, placeName, hours) {
  const s = fc.summary || {};
  const flags = [];
  if (s.thunderstorm) flags.push(["гроза", "bad"]);
  if (s.max_precip_prob_pct >= 60) flags.push([`дождь до ${s.max_precip_prob_pct}%`, "bad"]);
  else if (s.max_precip_prob_pct >= 30) flags.push([`возможен дождь ${s.max_precip_prob_pct}%`, ""]);
  if (s.max_gusts_kmh >= 35) flags.push([`${windFlagText(s.max_gusts_kmh)} ${Math.round(s.max_gusts_kmh)} км/ч`, s.max_gusts_kmh >= 45 ? "bad" : ""]);
  if (s.feels_like_min_c != null && s.feels_like_min_c < 5) flags.push(["холодно", ""]);
  if (s.temp_range_c && s.temp_range_c[1] >= 28) flags.push(["жара", s.temp_range_c[1] >= 33 ? "bad" : ""]);

  const t = s.temp_range_c || [];
  const rows = fc.hourly.map((h) => `<tr><td>${h.time}</td><td>${Math.round(h.temp_c)}° <span class="cond">(${Math.round(h.feels_like_c)}°)</span></td>
      <td>${h.precip_prob_pct ?? "—"}%</td><td>${Math.round(h.wind_kmh)}/${Math.round(h.gusts_kmh)} ${h.wind_from}</td><td class="cond">${esc(h.conditions)}</td></tr>`).join("");
  $("fc-result").innerHTML = `<div class="fc-result">
    <div class="fc-summary"><strong>${esc(placeName)}, ${fc.date} (${fc.weekday})</strong><br>
      ${[t[0] != null ? `${Math.round(t[0])}…${Math.round(t[1])}°, ощущается от ${Math.round(s.feels_like_min_c)}°` : "",
         s.sunset ? `закат в ${s.sunset}` : ""].filter(Boolean).join(", ")}
      ${flags.length ? `<div class="fc-flags">${flags.map(([f, c]) => `<span class="flag ${c}">${f}</span>`).join("")}</div>` : ""}
    </div>
    <table class="fc-table"><thead><tr><th>Час</th><th>Темп.</th><th>Осадки</th><th>Ветер/порывы</th><th>Условия</th></tr></thead><tbody>${rows}</tbody></table>
    <button class="primary-btn fc-ask" id="fc-ask">Обсудить с тренером</button></div>`;

  $("fc-ask").onclick = () => {
    const time = $("fc-time").value.slice(0, 5);
    const human = fc.date === isoDay(0) ? "Сегодня" : fc.date === isoDay(1) ? "Завтра" : fc.date;
    closeWeather();
    send(`${human} в ${time} тренируюсь: место «${placeName}», около ${hours} ч. Что надеть и какую тренировку делать с учётом погоды и восстановления?`);
  };
}

function isoDay(offset) {
  const d = new Date(Date.now() + offset * 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function openWeather() {
  closeSide();
  if (!$("fc-date").value) $("fc-date").value = isoDay(1);
  $("fc-date").min = isoDay(0);
  $("fc-date").max = isoDay(15);
  await renderPlaces();
  $("weather-sheet").hidden = false;
  $("memory-backdrop").hidden = false;
}

function closeWeather() {
  $("weather-sheet").hidden = true;
  syncBackdrop();
}

function syncBackdrop() {
  const open = ["memory", "weather-sheet", "plan-sheet"].some((id) => !$(id).hidden);
  $("memory-backdrop").hidden = !open;
}

function initWeather() {
  $("open-weather").onclick = openWeather;
  $("weather-close").onclick = closeWeather;

  $("fc-form").onsubmit = async (e) => {
    e.preventDefault();
    const place = $("fc-place").value;
    if (!place) return;
    const hours = $("fc-hours").value;
    $("fc-result").innerHTML = `<p class="mem-hint">Загружаю прогноз…</p>`;
    try {
      const q = new URLSearchParams({ place, date: $("fc-date").value, start_time: $("fc-time").value.slice(0, 5), hours });
      renderForecast(await api("/api/weather?" + q), place, hours);
    } catch (err) {
      $("fc-result").innerHTML = `<p class="save-msg bad">Прогноз не загрузился: ${esc(err.message)}</p>`;
    }
  };

  $("geo-form").onsubmit = async (e) => {
    e.preventDefault();
    const q = $("geo-q").value.trim();
    if (!q) return;
    const box = $("geo-results");
    box.innerHTML = `<p class="mem-hint">Ищу…</p>`;
    try {
      const found = await api("/api/geocode?q=" + encodeURIComponent(q));
      if (!found.length) { box.innerHTML = `<p class="mem-hint">Ничего не нашлось. Попробуй другое написание или введи координаты.</p>`; return; }
      box.innerHTML = found.map((g, i) => `<button type="button" class="geo-opt" data-i="${i}">${esc(g.name)}<small>${esc(g.region)} · ${g.latitude}, ${g.longitude}</small></button>`).join("");
      box.querySelectorAll(".geo-opt").forEach((b) => (b.onclick = () => {
        const g = found[+b.dataset.i];
        $("pl-lat").value = g.latitude; $("pl-lon").value = g.longitude;
        if (!$("pl-name").value) $("pl-name").value = g.name;
        box.innerHTML = "";
        $("pl-name").focus(); $("pl-name").select();
      }));
    } catch (err) {
      box.innerHTML = `<p class="save-msg bad">Поиск не удался: ${esc(err.message)}</p>`;
    }
  };

  // Вставка «43.4291, 39.9215» в поле широты раскладывается на оба поля
  $("pl-lat").addEventListener("paste", (e) => {
    const text = (e.clipboardData || window.clipboardData).getData("text");
    const m = text.match(/(-?\d+(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d+(?:[.,]\d+)?)/);
    if (m) { e.preventDefault(); $("pl-lat").value = m[1].replace(",", "."); $("pl-lon").value = m[2].replace(",", "."); }
  });

  $("place-form").onsubmit = async (e) => {
    e.preventDefault();
    const name = $("pl-name").value.trim();
    const lat = parseCoord($("pl-lat").value), lon = parseCoord($("pl-lon").value);
    const msg = $("pl-msg");
    if (Number.isNaN(lat) || Number.isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      msg.textContent = "Проверь координаты: широта от −90 до 90, долгота от −180 до 180"; msg.className = "save-msg bad"; return;
    }
    try {
      await api("/api/places", { method: "POST", body: JSON.stringify({ name, latitude: lat, longitude: lon, note: $("pl-note").value }) });
      msg.textContent = `«${name}» сохранено`; msg.className = "save-msg ok";
      ["pl-name", "pl-lat", "pl-lon", "pl-note", "geo-q"].forEach((id) => ($(id).value = ""));
      renderPlaces(name);
    } catch (err) {
      msg.textContent = "Не сохранилось: " + err.message; msg.className = "save-msg bad";
    }
  };
}


// ── Последний заезд и ощущения ─────────────────────────

const FEEL = ["тяжело", "так себе", "нормально", "хорошо", "отлично"];

async function loadLastRide() {
  const box = $("last-ride");
  let data;
  try { data = await api("/api/latest-activity"); } catch { box.innerHTML = ""; return; }
  const a = data.activity;
  if (!a) { box.innerHTML = ""; return; }
  const fb = data.feedback;
  const noData = a.data_available === false;
  const name = noData ? "Тренировка из Strava" : (a.name || "Тренировка");
  const dur = a.duration_min || (fb && fb.manual_duration_min);
  const meta = [a.date, dur ? `${dur} мин` : "", a.load_tss ? `TSS ${a.load_tss}` : ""].filter(Boolean).join(", ");
  const fbText = fb && (fb.rpe || fb.feel)
    ? [fb.rpe ? `RPE ${fb.rpe}` : "", fb.feel ? FEEL[fb.feel - 1] : ""].filter(Boolean).join(", ") : "";
  box.innerHTML = `<div class="lr-title">Последний заезд</div>
    <div class="lr-name">${esc(name)}</div><div class="lr-meta">${esc(meta)}</div>
    ${fbText ? `<div class="lr-fb">${esc(fbText)}</div>` : ""}
    ${fb && fb.note ? `<div class="lr-meta">${esc(fb.note)}</div>` : ""}
    ${noData && !(fb && fb.manual_duration_min) ? `<div class="lr-meta">Данных нет, можно вписать вручную</div>` : ""}
    <button class="lr-btn" id="lr-open">${fbText ? "Изменить оценку" : "Как прошло?"}</button>
    <div id="lr-form-box"></div>`;
  $("lr-open").onclick = () => showFeedbackForm(a, fb, noData);
}

function showFeedbackForm(a, fb, noData) {
  $("lr-open").hidden = true;
  let rpe = fb && fb.rpe, feel = fb && fb.feel;
  const box = $("lr-form-box");
  box.innerHTML = `<form class="lr-form" id="lr-form">
      <span class="lr-label">Насколько тяжело, 1–10</span>
      <div class="chips" id="lr-rpe">${[...Array(10)].map((_, i) => `<button type="button" class="chip" data-v="${i + 1}">${i + 1}</button>`).join("")}</div>
      <span class="lr-label">Самочувствие</span>
      <div class="chips" id="lr-feel">${FEEL.map((f, i) => `<button type="button" class="chip wide" data-v="${i + 1}">${f}</button>`).join("")}</div>
      ${noData ? `<div class="lr-row"><input id="lr-dur" inputmode="numeric" placeholder="минут" value="${fb && fb.manual_duration_min || ""}"><input id="lr-hr" inputmode="numeric" placeholder="ср. пульс" value="${fb && fb.manual_avg_hr || ""}"></div>` : ""}
      <input id="lr-note" placeholder="Комментарий: ноги, дыхание, что мешало" value="${esc(fb && fb.note || "")}">
      <div class="lr-actions"><button type="submit" class="primary-btn">Сохранить</button><button type="button" class="link-btn" id="lr-cancel">Отмена</button></div>
    </form>`;
  const mark = (id, val) => $(id).querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", +c.dataset.v === val));
  mark("lr-rpe", rpe); mark("lr-feel", feel);
  $("lr-rpe").onclick = (e) => { if (e.target.dataset.v) { rpe = +e.target.dataset.v; mark("lr-rpe", rpe); } };
  $("lr-feel").onclick = (e) => { if (e.target.dataset.v) { feel = +e.target.dataset.v; mark("lr-feel", feel); } };
  $("lr-cancel").onclick = loadLastRide;
  $("lr-form").onsubmit = async (e) => {
    e.preventDefault();
    const body = { activity_id: a.id, note: $("lr-note").value.trim() };
    if (rpe) body.rpe = rpe;
    if (feel) body.feel = feel;
    if (noData) {
      const d = parseInt($("lr-dur").value, 10), h = parseInt($("lr-hr").value, 10);
      if (d) body.duration_min = d;
      if (h) body.avg_hr = h;
    }
    try { await api("/api/feedback", { method: "POST", body: JSON.stringify(body) }); loadLastRide(); }
    catch (err) { alert("Не сохранилось: " + err.message); }
  };
}

// ── Брифинг и разбор недели ────────────────────────────

async function openSpecial(kind) {
  if (busy) return;
  closeSide();
  const r = await api(`/api/special/${kind}`, { method: "POST" });
  const conv = await openConversation(r.id);
  if (r.created) send(r.message);
  else if (conv.needs_answer && !conv.running) retryAnswer(); // прошлая попытка сорвалась — перезапускаем сами
}

// ── План ────────────────────────────────────────────────

const STATUS_LABELS = { planned: "запланировано", done: "выполнено", partial: "частично", missed: "пропущено", skipped: "отменено", moved: "перенесено" };
const WEEKDAYS_FULL = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"];
const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];

function dayLabel(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return `${WEEKDAYS_FULL[dt.getDay()]}, ${d} ${MONTHS_GEN[m - 1]}`;
}

async function renderPlan() {
  const body = $("plan-body");
  body.innerHTML = `<p class="mem-hint">Загружаю…</p>`;
  let data;
  try { data = await api(`/api/plan?date_from=${isoDay(-7)}&date_to=${isoDay(28)}`); }
  catch (err) { body.innerHTML = `<p class="save-msg bad">${esc(err.message)}</p>`; return; }
  if (!data.workouts.length) {
    body.innerHTML = `<p class="mem-hint">План пуст. Нажми кнопку выше или напиши тренеру, например: «составь план на две недели, 6 часов в неделю, длинная в субботу».</p>`;
    return;
  }
  const byDay = {};
  data.workouts.forEach((w) => (byDay[w.date] = byDay[w.date] || []).push(w));
  const today = isoDay(0);
  body.innerHTML = Object.keys(byDay).sort().map((day) => `
    <div class="plan-day"><div class="plan-day-head ${day === today ? "is-today" : ""}">${day === today ? "Сегодня, " + dayLabel(day).toLowerCase() : dayLabel(day)}</div>
    ${byDay[day].map((w) => {
      const meta = [w.duration_min ? `${w.duration_min} мин` : "", w.target_tss ? `TSS ${w.target_tss}` : "",
        w.indoor ? "станок" : (w.place || ""), w.start_time || ""].filter(Boolean).join(", ");
      const st = w.status || "planned";
      return `<div class="plan-item st-${st}">
        <div class="pi-top"><span class="pi-title">${esc(w.title)}</span><span class="status-tag ${st}">${STATUS_LABELS[st] || st}</span></div>
        ${meta ? `<div class="pi-meta">${esc(meta)}</div>` : ""}
        ${w.description ? `<div class="pi-desc">${esc(w.description)}</div>` : ""}
        <div class="pi-actions">
          <select data-status="${w.id}" aria-label="Статус">${Object.entries(STATUS_LABELS).map(([k, v]) => `<option value="${k}" ${k === st ? "selected" : ""}>${v}</option>`).join("")}</select>
          <button class="mem-del" data-remove="${w.id}">Удалить</button>
        </div></div>`;
    }).join("")}</div>`).join("");
  body.querySelectorAll("[data-status]").forEach((sel) => (sel.onchange = async () => {
    await api(`/api/plan/${sel.dataset.status}`, { method: "PATCH", body: JSON.stringify({ status: sel.value }) });
    renderPlan();
  }));
  body.querySelectorAll("[data-remove]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Удалить тренировку из плана?")) return;
    await api(`/api/plan/${b.dataset.remove}`, { method: "DELETE" });
    renderPlan();
  }));
}

async function openPlan() {
  closeSide();
  $("plan-sheet").hidden = false;
  syncBackdrop();
  renderPlan();
}

function closePlan() { $("plan-sheet").hidden = true; syncBackdrop(); }

// ── Запуск ──────────────────────────────────────────────

async function init() {
  const input = $("input");
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = input.scrollHeight + "px"; });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("composer").requestSubmit(); }
  });
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = ""; input.style.height = "auto";
    send(text);
  });
  $("new-chat").onclick = () => { currentId = null; closeSide(); showEmpty(); loadConversations(); input.focus(); };
  $("open-memory").onclick = openMemory;
  $("memory-close").onclick = closeMemory;
  $("memory-backdrop").onclick = () => { closeWeather(); closePlan(); closeMemory(); };
  $("brief-btn").onclick = () => openSpecial("brief");
  $("review-btn").onclick = () => openSpecial("review");
  $("open-plan").onclick = openPlan;
  $("plan-close").onclick = closePlan;
  $("plan-ask").onclick = () => {
    closePlan();
    currentId = null;
    showEmpty();
    send("Составь мне план на следующую неделю с учётом текущей формы, восстановления и моих мест и добавь его в план.");
  };
  initWeather();
  $("today-refresh").onclick = () => loadToday(true);
  $("side-open").onclick = () => $("side").classList.add("open");
  $("side-close").onclick = closeSide;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeWeather(); closePlan(); closeMemory(); closeSide(); } });

  try {
    const s = await api("/api/status");
    const missing = [!s.anthropic_key && "ANTHROPIC_API_KEY", !s.intervals_key && "ключи Intervals.icu"].filter(Boolean);
    if (missing.length) { $("status").textContent = "Не заданы в .env: " + missing.join(", "); $("status").className = "status bad"; }
    else $("status").textContent = s.model;
  } catch { $("status").textContent = "Сервер недоступен"; $("status").className = "status bad"; }

  loadToday();
  loadLastRide();
  const list = await loadConversations();
  if (list.length) openConversation(list[0].id); else showEmpty();
}

init();
