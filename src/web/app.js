"use strict";

// ---------- icons (inline SVG, stroke style) ----------

const ICONS = {
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  arrow: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m19 6-1 14H6L5 6"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
};

function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ` +
    `stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
}

document.querySelectorAll("[data-icon]").forEach((el) => {
  el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon));
});

// ---------- helpers ----------

const $ = (id) => document.getElementById(id);

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* not JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function remember(key, value) {
  try { localStorage.setItem(key, value); } catch (_) { /* storage unavailable */ }
}

function recall(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}

// The model's answer: a little Markdown (paragraphs, lists, bold, code),
// everything else escaped.
function renderMarkdown(text) {
  const inline = (line) => escapeHtml(line)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  const blocks = [];
  let list = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) blocks.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list) blocks.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`);
    list = null;
  };

  for (const raw of String(text).split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      flushParagraph();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
      list.items.push((bullet || numbered)[1]);
    } else if (!line.trim()) {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}

const SQL_KEYWORDS = [
  "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "ON",
  "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "AS", "AND", "OR", "NOT", "IN", "IS",
  "NULL", "DISTINCT", "WITH", "UNION", "ALL", "CASE", "WHEN", "THEN", "ELSE", "END", "DESC",
  "ASC", "BETWEEN", "LIKE", "ILIKE", "EXISTS", "COUNT", "SUM", "AVG", "MIN", "MAX", "OVER",
  "PARTITION", "EXTRACT", "CAST", "COALESCE", "ROUND", "TRUE", "FALSE", "INTERVAL", "FILTER",
];
const SQL_TOKEN = new RegExp(
  `('(?:[^']|'')*')|(\\b\\d+(?:\\.\\d+)?\\b)|\\b(${SQL_KEYWORDS.join("|")})\\b`, "gi",
);

function highlightSql(sql) {
  let html = "";
  let last = 0;
  for (const match of sql.matchAll(SQL_TOKEN)) {
    html += escapeHtml(sql.slice(last, match.index));
    const kind = match[1] ? "string" : match[2] ? "number" : "keyword";
    html += `<span class="sql-${kind}">${escapeHtml(match[0])}</span>`;
    last = match.index + match[0].length;
  }
  return html + escapeHtml(sql.slice(last));
}

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("hu-HU", { month: "short", day: "numeric" });
}

// ---------- state ----------

const state = {
  datasets: [],
  dataset: null,
  conversationId: null,
  busy: false,
};

const app = $("app");
const thread = $("thread");
const chat = $("chat");
const input = $("input");
const send = $("send");

// ---------- sidebar ----------

const narrow = () => window.matchMedia("(max-width: 820px)").matches;

function setSidebar(open) {
  if (narrow()) {
    app.classList.toggle("mobile-open", open);
  } else {
    app.classList.toggle("collapsed", !open);
    remember("sidebar", open ? "open" : "closed");
  }
}

$("close-sidebar").onclick = () => setSidebar(false);
$("open-sidebar").onclick = () => setSidebar(true);
$("scrim").onclick = () => setSidebar(false);
if (recall("sidebar") === "closed") app.classList.add("collapsed");

async function loadHistory() {
  const list = $("history");
  let conversations = [];
  try {
    conversations = await api("/api/conversations");
  } catch (error) {
    list.innerHTML = `<div class="history-empty">Nem sikerült betölteni.</div>`;
    return;
  }

  list.innerHTML = "";
  if (!conversations.length) {
    list.innerHTML = `<div class="history-empty">Még nincs beszélgetés.</div>`;
    return;
  }

  for (const conversation of conversations) {
    const item = el("div", "history-item" + (conversation.id === state.conversationId ? " active" : ""));

    const open = el("button", "history-open",
      `<span class="history-title">${escapeHtml(conversation.title)}</span>` +
      `<span class="history-meta">${escapeHtml(datasetLabel(conversation.dataset))} · ${formatTime(conversation.created_at)}</span>`);
    open.title = conversation.title;
    open.onclick = () => openConversation(conversation.id);

    const remove = el("button", "history-delete", icon("trash"));
    remove.title = "Beszélgetés törlése";
    remove.onclick = async (event) => {
      event.stopPropagation();
      if (!confirm(`Törlöd ezt a beszélgetést?\n\n„${conversation.title}”`)) return;
      await api(`/api/conversations/${conversation.id}`, { method: "DELETE" });
      if (conversation.id === state.conversationId) newChat();
      loadHistory();
    };

    item.append(open, remove);
    list.append(item);
  }
}

// ---------- dataset picker ----------

const datasetBox = $("dataset");

const datasetLabel = (name) => (state.datasets.find((d) => d.name === name) || {}).label || name;

function setDataset(name) {
  state.dataset = name;
  $("dataset-name").textContent = datasetLabel(name);
  const dataset = state.datasets.find((d) => d.name === name);

  const suggestions = $("suggestions");
  suggestions.innerHTML = "";
  for (const question of dataset ? dataset.examples : []) {
    const button = el("button", "suggestion");
    button.textContent = question;
    button.onclick = () => ask(question);
    suggestions.append(button);
  }

  document.querySelectorAll(".dataset-option").forEach((option) => {
    option.classList.toggle("selected", option.dataset.name === name);
  });
}

function setMenu(open) {
  datasetBox.classList.toggle("open", open);
  $("dataset-btn").setAttribute("aria-expanded", String(open));
  if (open) {
    const selected = datasetBox.querySelector(".dataset-option.selected") || datasetBox.querySelector(".dataset-option");
    if (selected) selected.focus();
  }
}

// Picking another database inside a conversation starts a new one:
// a conversation is about one database.
function chooseDataset(name) {
  setMenu(false);
  remember("dataset", name);
  if (state.conversationId !== null && name !== state.dataset) newChat(name);
  else setDataset(name);
  input.focus();
}

$("dataset-btn").onclick = (event) => {
  event.stopPropagation();
  if (!state.busy) setMenu(!datasetBox.classList.contains("open"));
};
document.addEventListener("click", () => setMenu(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && datasetBox.classList.contains("open")) {
    setMenu(false);
    $("dataset-btn").focus();
  }
});

async function loadDatasets() {
  const { default: fallback, datasets } = await api("/api/datasets");
  // Older servers sent only name + description.
  state.datasets = datasets.map((d) => ({
    ...d,
    label: d.label || d.name,
    summary: d.summary || d.description || "",
  }));

  const menu = $("dataset-menu");
  menu.append(el("div", "dataset-menu-title", "Melyik adatbázisról kérdezel?"));
  for (const dataset of state.datasets) {
    const option = el("button", "dataset-option",
      `<span class="dataset-option-text"><strong>${escapeHtml(dataset.label)}</strong>` +
      `<small>${escapeHtml(dataset.summary)}</small></span>` +
      `<span class="dataset-check">${icon("check")}</span>`);
    option.dataset.name = dataset.name;
    option.setAttribute("role", "menuitemradio");
    option.onclick = (event) => {
      event.stopPropagation();
      chooseDataset(dataset.name);
    };
    menu.append(option);
  }
  menu.append(el("div", "dataset-hint", "Beszélgetés közben váltva új beszélgetés indul."));

  const saved = recall("dataset");
  setDataset(datasets.some((d) => d.name === saved) ? saved : fallback);
}

// ---------- messages ----------

function showEmpty(empty) {
  $("empty").hidden = !empty;
}

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function addUserMessage(text) {
  const message = el("div", "message user");
  const bubble = el("div", "bubble");
  bubble.textContent = text;
  message.append(bubble);
  thread.append(message);
}

function assistantShell() {
  const message = el("div", "message assistant");
  message.append(el("div", "avatar", icon("database")));
  const body = el("div", "assistant-body");
  message.append(body);
  thread.append(message);
  return body;
}

function addThinking() {
  const body = assistantShell();
  body.innerHTML =
    `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span>` +
    `<span>Gondolkodom</span><span class="thinking-time"></span></div>`;
  const started = Date.now();
  const time = body.querySelector(".thinking-time");
  const timer = setInterval(() => {
    time.textContent = `${Math.round((Date.now() - started) / 1000)} s`;
  }, 1000);
  return { body, stop: () => clearInterval(timer) };
}

function fillAssistant(body, message) {
  const details = message.details || {};
  const failed = !details.columns;
  body.innerHTML = "";
  body.append(el("div", "answer" + (failed ? " failed" : ""), renderMarkdown(message.content)));

  if (!details.sql && !details.error) return;

  const toggle = el("button", "details-toggle", `<span>Részletek</span>${icon("chevron")}`);
  toggle.setAttribute("aria-expanded", "false");
  const panel = el("div", "details");
  panel.hidden = true;
  toggle.onclick = () => {
    if (!panel.childElementCount) buildDetails(panel, details);
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  };
  body.append(toggle, panel);
}

function buildDetails(panel, details) {
  const chips = [];
  if (details.tables) chips.push(`Táblák: ${details.tables.join(", ")}`);
  else if (details.table_count) chips.push(`Teljes séma · ${details.table_count} tábla`);
  if (details.correction_rounds) chips.push(`${details.correction_rounds} javítás`);
  if (details.seconds != null) chips.push(`${details.seconds} s`);
  if (chips.length) {
    panel.append(el("div", "chips", chips.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")));
  }

  if (details.sql) {
    const block = el("div", "code-block");
    const head = el("div", "code-head", "<span>SQL</span>");
    const copy = el("button", "copy", `${icon("copy")}<span>Másolás</span>`);
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(details.sql);
        copy.innerHTML = `${icon("check")}<span>Másolva</span>`;
        setTimeout(() => { copy.innerHTML = `${icon("copy")}<span>Másolás</span>`; }, 1500);
      } catch (_) { /* clipboard unavailable */ }
    };
    head.append(copy);
    const pre = el("pre", "", highlightSql(details.sql));
    block.append(head, pre);
    panel.append(block);
  }

  if (details.error) panel.append(el("div", "error-box", escapeHtml(details.error)));

  if (details.columns) {
    const numeric = details.columns.map((_, i) => details.rows.length > 0 &&
      details.rows.every((row) => row[i] === null || typeof row[i] === "number"));
    const header = details.columns.map((c, i) => `<th${numeric[i] ? ' class="num"' : ""}>${escapeHtml(c)}</th>`).join("");
    const body = details.rows.map((row) => "<tr>" + row.map((value) => {
      if (value === null) return `<td class="null">NULL</td>`;
      const numeric = typeof value === "number";
      return `<td${numeric ? ' class="num"' : ""}>${escapeHtml(value)}</td>`;
    }).join("") + "</tr>").join("");
    const wrap = el("div", "table-wrap",
      `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`);
    panel.append(wrap);

    if (!details.rows.length) panel.append(el("div", "table-note", "A lekérdezés nem adott vissza sort."));
    else if (details.row_count > details.rows.length) {
      panel.append(el("div", "table-note", `Az első ${details.rows.length} sor, összesen ${details.row_count}.`));
    } else {
      panel.append(el("div", "table-note", `${details.row_count} sor`));
    }
  }
}

function addAssistantMessage(message) {
  fillAssistant(assistantShell(), message);
}

// ---------- conversations ----------

function newChat(dataset) {
  state.conversationId = null;
  history.replaceState(null, "", location.pathname);
  thread.innerHTML = "";
  showEmpty(true);
  const name = typeof dataset === "string" ? dataset : recall("dataset");
  if (name && state.datasets.some((d) => d.name === name)) setDataset(name);
  loadHistory();
  if (narrow()) setSidebar(false);
  input.focus();
}

async function openConversation(id) {
  if (state.busy) return;
  try {
    const conversation = await api(`/api/conversations/${id}`);
    state.conversationId = conversation.id;
    history.replaceState(null, "", `#${conversation.id}`);
    setDataset(conversation.dataset);
    thread.innerHTML = "";
    showEmpty(false);
    for (const message of conversation.messages) {
      if (message.role === "user") addUserMessage(message.content);
      else addAssistantMessage(message);
    }
    loadHistory();
    if (narrow()) setSidebar(false);
    requestAnimationFrame(scrollToBottom);
  } catch (error) {
    newChat();
  }
}

$("new-chat").onclick = () => newChat();

// ---------- asking ----------

function setBusy(busy) {
  state.busy = busy;
  send.disabled = busy || !input.value.trim();
  datasetBox.classList.toggle("disabled", busy);
  if (busy) setMenu(false);
}

async function ask(question) {
  question = question.trim();
  if (!question || state.busy) return;

  setBusy(true);
  showEmpty(false);
  addUserMessage(question);
  const thinking = addThinking();
  scrollToBottom();

  try {
    const result = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        dataset: state.dataset,
        conversation_id: state.conversationId,
      }),
    });
    state.conversationId = result.conversation.id;
    history.replaceState(null, "", `#${result.conversation.id}`);
    thinking.stop();
    fillAssistant(thinking.body, result.message);
    loadHistory();
  } catch (error) {
    thinking.stop();
    fillAssistant(thinking.body, {
      content: "Nem sikerült elérni a szervert. Fut még a `web_app.py`?",
      details: { error: error.message },
    });
  } finally {
    setBusy(false);
    scrollToBottom();
    input.focus();
  }
}

// ---------- composer ----------

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 200) + "px";
}

input.addEventListener("input", () => {
  autosize();
  send.disabled = state.busy || !input.value.trim();
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("composer").requestSubmit();
  }
});

$("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value;
  if (!question.trim() || state.busy) return;
  input.value = "";
  autosize();
  ask(question);
});

// ---------- start ----------

(async () => {
  try {
    await loadDatasets();
  } catch (error) {
    $("empty-description").textContent = "A szerver nem érhető el.";
  }
  const opened = Number(location.hash.slice(1));
  if (opened) await openConversation(opened);
  else loadHistory();
  input.focus();
})();
