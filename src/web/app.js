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
  bug: '<path d="m8 2 1.9 1.9"/><path d="M14.1 3.9 16 2"/><path d="M9 7.1V6a3 3 0 1 1 6 0v1.1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.5 13H3"/><path d="M21 13h-3.5"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
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


// ---------- interface language ----------

// The model answers in the language of the question whatever is chosen
// here; this only switches the app's own texts.
const STRINGS = {
  hu: {
    locale: "hu-HU",
    language: "Nyelv",
    closeSidebar: "Oldalsáv bezárása",
    openSidebar: "Oldalsáv megnyitása",
    newChat: "Új beszélgetés",
    history: "Előzmények",
    historyFailed: "Nem sikerült betölteni.",
    historyEmpty: "Még nincs beszélgetés.",
    deleteChat: "Beszélgetés törlése",
    confirmDelete: (title) => `Törlöd ezt a beszélgetést?\n\n„${title}”`,
    database: "Adatbázis",
    whichDatabase: "Melyik adatbázisról kérdezel?",
    switchHint: "Beszélgetés közben váltva új beszélgetés indul.",
    welcome: "Miről kérdeznél?",
    welcomeText: "Kérdezz természetes nyelven: SQL-t írok belőle, lefuttatom, és elmondom az eredményt.",
    placeholder: "Kérdezz az adatbázisról…",
    send: "Küldés (Enter)",
    disclaimer: "A választ egy helyi nyelvi modell generálja. Az SQL a „Részletek” alatt ellenőrizhető.",
    thinking: "Gondolkodom",
    details: "Részletek",
    tables: (list) => `Táblák: ${list}`,
    fullSchema: (count) => `Teljes séma · ${count} tábla`,
    corrections: (count) => `${count} javítás`,
    copy: "Másolás",
    copied: "Másolva",
    noRows: "A lekérdezés nem adott vissza sort.",
    firstRows: (shown, total) => `Az első ${shown} sor, összesen ${total}.`,
    rows: (count) => `${count} sor`,
    serverDown: "Nem sikerült elérni a szervert. Fut még a `web_app.py`?",
    serverUnavailable: "A szerver nem érhető el.",
    debug: "Debug",
    debugTitle: "Fejlesztői nézet: minden lépés részletei",
    doubtful: "Ellenőrizd: az eredmény lehet, hogy nem a kérdésre válaszol",
    moreRows: (count) => `+ ${count} további sor a részletekben`,
    attempts: "Próbálkozások",
    attempt: (n, total, ok) => `${n}/${total}. próbálkozás${ok ? "" : " – hibás"}`,
    candidates: (list) => `Jelöltek: ${list}`,
    steps: "Lépések és költség",
    tokens: (sql, answer) => `Token: SQL ${sql}, válasz ${answer}`,
    setup: "Beállítás",
  },
  en: {
    locale: "en-GB",
    language: "Language",
    closeSidebar: "Close sidebar",
    openSidebar: "Open sidebar",
    newChat: "New chat",
    history: "History",
    historyFailed: "Could not load.",
    historyEmpty: "No conversations yet.",
    deleteChat: "Delete conversation",
    confirmDelete: (title) => `Delete this conversation?\n\n“${title}”`,
    database: "Database",
    whichDatabase: "Which database are you asking about?",
    switchHint: "Switching during a conversation starts a new one.",
    welcome: "What would you like to know?",
    welcomeText: "Ask in plain language: I write the SQL, run it and tell you the result.",
    placeholder: "Ask about the database…",
    send: "Send (Enter)",
    disclaimer: "Answers are generated by a local language model. Check the SQL under “Details”.",
    thinking: "Thinking",
    details: "Details",
    tables: (list) => `Tables: ${list}`,
    fullSchema: (count) => `Full schema · ${count} tables`,
    corrections: (count) => `${count} correction${count === 1 ? "" : "s"}`,
    copy: "Copy",
    copied: "Copied",
    noRows: "The query returned no rows.",
    firstRows: (shown, total) => `First ${shown} of ${total} rows.`,
    rows: (count) => `${count} row${count === 1 ? "" : "s"}`,
    serverDown: "Could not reach the server. Is `web_app.py` still running?",
    serverUnavailable: "The server is not reachable.",
    debug: "Debug",
    debugTitle: "Developer view: every step in detail",
    doubtful: "Check this: the result may not answer the question",
    moreRows: (count) => `+ ${count} more row${count === 1 ? "" : "s"} in the details`,
    attempts: "Attempts",
    attempt: (n, total, ok) => `Attempt ${n}/${total}${ok ? "" : " – failed"}`,
    candidates: (list) => `Candidates: ${list}`,
    steps: "Steps and cost",
    tokens: (sql, answer) => `Tokens: SQL ${sql}, answer ${answer}`,
    setup: "Setup",
  },
};
const LANGUAGES = Object.keys(STRINGS);

function t(key, ...args) {
  const text = STRINGS[state.language][key];
  return typeof text === "function" ? text(...args) : text;
}

function applyStaticTexts() {
  document.documentElement.lang = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => { node.title = t(node.dataset.i18nTitle); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => { node.setAttribute("aria-label", t(node.dataset.i18nAria)); });
  document.querySelectorAll(".flag").forEach((flag) => {
    const active = flag.dataset.language === state.language;
    flag.classList.toggle("active", active);
    flag.setAttribute("aria-pressed", String(active));
  });
}

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString(t("locale"), { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(t("locale"), { month: "short", day: "numeric" });
}

// ---------- state ----------

const savedLanguage = recall("language");

const state = {
  language: LANGUAGES.includes(savedLanguage) ? savedLanguage : "hu",
  debug: recall("debug") === "on",
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
    list.innerHTML = `<div class="history-empty">${escapeHtml(t("historyFailed"))}</div>`;
    return;
  }

  list.innerHTML = "";
  if (!conversations.length) {
    list.innerHTML = `<div class="history-empty">${escapeHtml(t("historyEmpty"))}</div>`;
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
    remove.title = t("deleteChat");
    remove.onclick = async (event) => {
      event.stopPropagation();
      if (!confirm(t("confirmDelete", conversation.title))) return;
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

// Names, summaries and suggested questions come in the interface language.
async function loadDatasets() {
  const { default: fallback, datasets } = await api(`/api/datasets?language=${state.language}`);
  // Older servers sent only name + description.
  state.datasets = datasets.map((d) => ({
    ...d,
    label: d.label || d.name,
    summary: d.summary || d.description || "",
  }));

  const menu = $("dataset-menu");
  menu.innerHTML = "";
  menu.append(el("div", "dataset-menu-title", escapeHtml(t("whichDatabase"))));
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
  menu.append(el("div", "dataset-hint", escapeHtml(t("switchHint"))));

  const known = (name) => state.datasets.some((d) => d.name === name);
  const saved = recall("dataset");
  setDataset(known(state.dataset) ? state.dataset : known(saved) ? saved : fallback);
}

// ---------- language switch ----------

async function setLanguage(language) {
  if (state.busy || language === state.language || !LANGUAGES.includes(language)) return;
  state.language = language;
  remember("language", language);
  applyStaticTexts();
  try { await loadDatasets(); } catch (_) { /* keep the old names */ }
  // Re-render what is on screen in the new language.
  if (state.conversationId !== null) await openConversation(state.conversationId);
  else loadHistory();
}

document.querySelectorAll(".flag").forEach((flag) => {
  flag.onclick = () => setLanguage(flag.dataset.language);
});

// ---------- debug view ----------

// Off: the answer, a short preview of the rows and closed details.
// On: the details open by default, with every attempt, the candidate
// tables, timings, tokens and the setup.
function applyDebug() {
  $("debug-toggle").setAttribute("aria-pressed", String(state.debug));
}

$("debug-toggle").onclick = async () => {
  if (state.busy) return;
  state.debug = !state.debug;
  remember("debug", state.debug ? "on" : "off");
  applyDebug();
  if (state.conversationId !== null) await openConversation(state.conversationId);
};

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
    `<span>${escapeHtml(t("thinking"))}</span><span class="thinking-time"></span></div>`;
  const started = Date.now();
  const time = body.querySelector(".thinking-time");
  const timer = setInterval(() => {
    time.textContent = `${Math.round((Date.now() - started) / 1000)} s`;
  }, 1000);
  return { body, stop: () => clearInterval(timer) };
}

const PREVIEW_ROWS = 5;

function fillAssistant(body, message) {
  const details = message.details || {};
  const failed = !details.columns;
  body.innerHTML = "";
  if (details.doubtful) {
    body.append(el("div", "doubt", `${icon("alert")}<span>${escapeHtml(t("doubtful"))}</span>`));
  }
  body.append(el("div", "answer" + (failed ? " failed" : ""), renderMarkdown(message.content)));

  // The first rows under the answer, so a strange result is visible at
  // once; a single value is already in the answer.
  const single = details.columns && details.columns.length === 1 && details.row_count === 1;
  if (!state.debug && details.columns && details.rows.length && !single) {
    const preview = el("div", "preview");
    preview.append(resultTable(details, PREVIEW_ROWS));
    if (details.row_count > PREVIEW_ROWS) {
      preview.append(el("div", "table-note", escapeHtml(t("moreRows", details.row_count - PREVIEW_ROWS))));
    }
    body.append(preview);
  }

  if (!details.sql && !details.error) return;

  const toggle = el("button", "details-toggle", `<span>${escapeHtml(t("details"))}</span>${icon("chevron")}`);
  const panel = el("div", "details");
  const setOpen = (open) => {
    if (open && !panel.childElementCount) buildDetails(panel, details);
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  };
  toggle.onclick = () => setOpen(panel.hidden);
  setOpen(state.debug);
  body.append(toggle, panel);
}

function resultTable(details, limit) {
  const rows = details.rows.slice(0, limit);
  const numeric = details.columns.map((_, i) => rows.length > 0 &&
    rows.every((row) => row[i] === null || typeof row[i] === "number"));
  const header = details.columns.map((c, i) => `<th${numeric[i] ? ' class="num"' : ""}>${escapeHtml(c)}</th>`).join("");
  const body = rows.map((row) => "<tr>" + row.map((value) => {
    if (value === null) return `<td class="null">NULL</td>`;
    const isNumber = typeof value === "number";
    return `<td${isNumber ? ' class="num"' : ""}>${escapeHtml(value)}</td>`;
  }).join("") + "</tr>").join("");
  return el("div", "table-wrap", `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`);
}

function sqlBlock(sql, title) {
  const block = el("div", "code-block");
  const head = el("div", "code-head", `<span>${escapeHtml(title)}</span>`);
  const copyLabel = () => `${icon("copy")}<span>${escapeHtml(t("copy"))}</span>`;
  const copy = el("button", "copy", copyLabel());
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      copy.innerHTML = `${icon("check")}<span>${escapeHtml(t("copied"))}</span>`;
      setTimeout(() => { copy.innerHTML = copyLabel(); }, 1500);
    } catch (_) { /* clipboard unavailable */ }
  };
  head.append(copy);
  block.append(head, el("pre", "", highlightSql(sql)));
  return block;
}

function chipRow(texts, extraClass = "") {
  return el("div", "chips", texts.map((c) => `<span class="chip ${extraClass}">${escapeHtml(c)}</span>`).join(""));
}

function debugSection(title, ...children) {
  const section = el("div", "debug-section");
  section.append(el("div", "debug-title", escapeHtml(title)), ...children);
  return section;
}

function buildDetails(panel, details) {
  const chips = [];
  if (details.tables) chips.push(t("tables", details.tables.join(", ")));
  else if (details.table_count) chips.push(t("fullSchema", details.table_count));
  if (details.correction_rounds) chips.push(t("corrections", details.correction_rounds));
  if (details.seconds != null) chips.push(`${details.seconds} s`);
  if (chips.length) {
    panel.append(el("div", "chips", chips.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")));
  }

  const attempts = details.attempts || [];
  if (state.debug && attempts.length > 1) {
    // Every try with its error; the last one is the final SQL below.
    const tries = attempts.slice(0, -1).flatMap((attempt, i) => [
      sqlBlock(attempt.sql, t("attempt", i + 1, attempts.length, false)),
      el("div", "error-box", escapeHtml(attempt.error)),
    ]);
    panel.append(debugSection(t("attempts"), ...tries));
  }

  if (details.sql) {
    const title = state.debug && attempts.length > 1
      ? t("attempt", attempts.length, attempts.length, !details.error)
      : "SQL";
    panel.append(sqlBlock(details.sql, title));
  }

  if (details.error) panel.append(el("div", "error-box", escapeHtml(details.error)));

  if (details.columns) {
    panel.append(resultTable(details, details.rows.length));

    let note;
    if (!details.rows.length) note = t("noRows");
    else if (details.row_count > details.rows.length) note = t("firstRows", details.rows.length, details.row_count);
    else note = t("rows", details.row_count);
    panel.append(el("div", "table-note", escapeHtml(note)));
  }

  if (state.debug) {
    const steps = [];
    if (details.candidate_tables) steps.push(t("candidates", details.candidate_tables.join(", ")));
    for (const [key, seconds] of Object.entries(details.timings || {})) steps.push(`${key} ${seconds} s`);
    if (details.tokens) steps.push(t("tokens", details.tokens.prompt + details.tokens.completion, details.tokens.answer));
    if (details.doubtful !== undefined && details.doubtful !== null) steps.push(`check: ${details.doubtful ? "DOUBTFUL" : "OK"}`);
    if (steps.length) panel.append(debugSection(t("steps"), chipRow(steps, "debug")));

    if (details.config) {
      const setup = Object.entries(details.config).map(([key, value]) => `${key}: ${value}`);
      panel.append(debugSection(t("setup"), chipRow(setup, "debug")));
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
  $("language").classList.toggle("disabled", busy);
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
        language: state.language,
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
      content: t("serverDown"),
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
  applyStaticTexts();
  applyDebug();
  try {
    await loadDatasets();
  } catch (error) {
    $("empty-description").textContent = t("serverUnavailable");
  }
  const opened = Number(location.hash.slice(1));
  if (opened) await openConversation(opened);
  else loadHistory();
  input.focus();
})();
