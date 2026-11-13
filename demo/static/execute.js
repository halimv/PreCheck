// Execute page: pick a protocol from healed/, walk through the deck setup checklist built from
// the deck config and the passing IR, then run it on the STARlet (or a ChatterBox rehearsal).

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const state = { detail: null, checked: new Set(), exId: null, source: null, timer: null, layout: null, remote: null };

// The backend radio is "<where>:<backend>": where is local or pi, backend chatterbox or star.
function choice() {
  const [where, backend] = document.querySelector("input[name=backend]:checked").value.split(":");
  return { where, backend };
}

// Why the Pi cannot run this now (the server checks the same before it starts), or "".
function piRefusal(backend) {
  const r = state.remote;
  if (!r || !r.configured) return "No Pi is configured (config/remote.json).";
  if (r.error) return r.error;
  if (!r.in_sync) return "The code on the Pi differs from this computer's: sync it.";
  if (backend === "star" && !r.star_connected) return `The STARlet is not on ${r.host}'s USB.`;
  if (backend === "star" && r.lock.held_by) return `Another program is driving the STARlet (pid ${r.lock.held_by}; the AHC bridge uses this lock). Stop it first.`;
  return "";
}
// el comes from common.js.

function setStatus(kind, label, text) {
  $("status-chip").className = `chip ${kind}`;
  $("status-chip").textContent = label;
  $("status-text").textContent = text;
}

function storageKey() { return `checklist:${state.detail.name}`; }

function loadChecked() {
  try { return new Set(JSON.parse(localStorage.getItem(storageKey()) || "[]")); } catch { return new Set(); }
}

function saveChecked() {
  try { localStorage.setItem(storageKey(), JSON.stringify([...state.checked])); } catch { /* storage unavailable */ }
}

// ---------- deck drawing ----------

function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

function drawDeck(deck, highlight) {
  const RAIL = 26, TOP = 18, H = 230, W = deck.num_rails * RAIL;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H + 46}`, class: "deck", role: "img", "aria-label": "Deck layout" });
  root.append(svg("text", { x: 4, y: 12, class: "deck-edge" }, "BACK"));
  root.append(svg("rect", { x: 0, y: TOP, width: W, height: H, class: "deck-bed", rx: 6 }));
  for (let r = 1; r <= deck.num_rails; r++) {
    const x = (r - 1) * RAIL;
    root.append(svg("line", { x1: x, y1: TOP, x2: x, y2: TOP + H, class: "deck-rail" }));
    if (r === 1 || r % 5 === 0) root.append(svg("text", { x: x + 3, y: TOP + H + 14, class: "deck-num" }, String(r)));
  }
  root.append(svg("text", { x: 4, y: TOP + H + 32, class: "deck-edge" }, "FRONT (operator side) · rail numbers along the bottom"));

  const showUse = deck.show_use !== false;
  for (const c of deck.carriers) {
    const x = (c.rails - 1) * RAIL + 2, w = c.width * RAIL - 4;
    const g = svg("g", { class: `deck-carrier${c.needed || !showUse ? "" : " unused"}${c.added ? " added" : ""}${highlight === c.name ? " current" : ""}` });
    g.append(svg("title", {}, `${c.factory} on rail ${c.rails}${c.added ? " (to add before the run)" : ""}`
      + `${showUse && !c.needed ? " (not used by this protocol)" : ""}`));
    g.append(svg("rect", { x, y: TOP + 4, width: w, height: H - 8, rx: 4, class: "deck-carrier-box" }));
    const siteH = (H - 16) / c.sites;
    for (const lw of c.labware) {
      // PLR site 0 is the front-most, so it is drawn at the bottom.
      const y = TOP + 8 + (c.sites - 1 - lw.slot) * siteH;
      g.append(svg("rect", { x: x + 3, y: y + 1, width: w - 6, height: Math.max(siteH - 2, 3), rx: 2,
        class: `deck-site${lw.used ? " used" : ""}${lw.added ? " added" : ""}` }));
      if (siteH >= 14) {
        const label = w > 60 ? lw.id : lw.id.slice(0, 6);
        g.append(svg("text", { x: x + 6, y: y + Math.min(siteH / 2 + 4, 16), class: "deck-label" }, label));
      } else {
        g.append(svg("text", { x: x + w + 3, y: y + siteH, class: "deck-label side" }, lw.id));
      }
    }
    root.append(g);
  }
  $("deck-svg").replaceChildren(root);
}

// ---------- checklist ----------

function currentItem() {
  return state.detail.setup.items.find((i) => !state.checked.has(i.id));
}

function renderChecklist() {
  const { items } = state.detail.setup;
  const current = currentItem();
  const list = $("checklist");
  list.replaceChildren();
  let group = null;
  for (const item of items) {
    if (item.group !== group) {
      group = item.group;
      list.append(el("li", { class: "check-group", text: group }));
    }
    const box = el("input", { type: "checkbox", id: `chk-${item.id}` });
    box.checked = state.checked.has(item.id);
    box.addEventListener("change", () => {
      if (box.checked) state.checked.add(item.id); else state.checked.delete(item.id);
      saveChecked();
      renderChecklist();
    });
    const li = el("li", { class: `check-item${box.checked ? " done" : ""}${item === current ? " current" : ""}` },
      box,
      el("label", { for: `chk-${item.id}` }, el("strong", { text: item.title }), el("span", { class: "muted", text: item.detail })));
    list.append(li);
  }
  const done = items.filter((i) => state.checked.has(i.id)).length;
  $("checklist-progress").textContent = `${done} of ${items.length} confirmed`;
  drawDeck(state.detail.real_deck.drawing, current && current.carrier);
  updateStart();
}

function updateStart() {
  const d = state.detail;
  const { where, backend } = choice();
  const allChecked = d && d.setup.items.every((i) => state.checked.has(i.id));
  const layoutMismatch = !!(state.layout && state.layout.comparison && !state.layout.comparison.ok);
  const piBlocked = where === "pi" ? piRefusal(backend) : "";
  const running = state.exId !== null;
  $("pi-panel").hidden = where !== "pi";
  let note = "";
  if (!d) note = "";
  else if (!d.gate.passed) note = `Blocked: the protocol fails stage "${d.gate.stage}": ${d.gate.summary}`;
  else if (piBlocked) note = `Blocked: ${piBlocked}`;
  else if (backend === "star" && layoutMismatch) note = `Blocked: the Venus layout ${state.layout.name} does not match this protocol's deck.`;
  else if (backend === "star" && !allChecked) note = "Confirm every setup item before running on the STARlet.";
  else if (backend === "star") note = "Starts the real instrument. Run the tip check first, with water before samples.";
  $("run-note").textContent = note;
  $("start").disabled = running || !d || !d.gate.passed || !!piBlocked
    || (backend === "star" && (!allChecked || layoutMismatch));
}

// ---------- protocol selection ----------

async function loadProtocol(name) {
  setStatus("running", "Checking", "Re-running the compiler and simulator on the healed protocol…");
  const res = await fetch(`/api/healed/${encodeURIComponent(name)}`);
  const d = await res.json();
  state.detail = d;
  state.checked = loadChecked();
  $("protocol-kv").hidden = false;
  $("p-name").textContent = d.protocol.protocol_name || d.name;
  $("p-steps").textContent = d.protocol.steps.length;
  $("p-gate").replaceChildren(el("span", { class: `badge ${d.gate.passed ? "ok" : "bad"}`, text: d.gate.passed ? "passed" : `failed (${d.gate.stage})` }));
  $("p-script").textContent = d.script;
  $("p-deck").textContent = d.deck_file;

  const assumptions = d.setup.assumptions || [];
  $("assumptions-panel").hidden = !assumptions.length && !(d.protocol.source || {}).text;
  $("assumptions").replaceChildren(...assumptions.map((a) => el("li", { text: a })));
  $("source-text").textContent = (d.protocol.source || {}).text || "";
  const revisions = d.protocol.revisions || [];
  $("revisions-block").hidden = !revisions.length;
  $("revisions").replaceChildren(...revisions.map((r) => el("li", { text: `${r.note} (on ${r.from})` })));
  if (revisions.length) $("assumptions-panel").hidden = false;

  const real = d.real_deck;
  $("deck-note-real").textContent = real.warning || "";
  $("deck-card").hidden = false;
  $("checklist-card").hidden = false;
  // The instrument library's VENUS layout is the default; a .lay loaded on this page replaces it.
  if (!state.layoutUploaded) state.layout = d.instrument_layout ? { id: d.instrument_layout } : null;
  if (state.layout) await refreshLayout(); else renderLayout();
  renderChecklist();
  if (d.gate.passed) setStatus("ok", "Passing", d.gate.summary);
  else setStatus("bad", "Blocked", d.gate.summary);
}

async function loadList() {
  const items = await (await fetch("/api/healed")).json();
  const select = $("healed");
  if (!items.length) {
    $("healed-note").textContent = "healed/ is empty. Run: python pipeline.py <protocol.pdf or text>";
    return;
  }
  for (const p of items) {
    const when = new Date(p.modified * 1000).toLocaleString();
    const revision = p.name.match(/_r(\d+)$/);
    const label = `${p.protocol_name}${revision ? ` (revision ${revision[1]})` : ""}`;
    select.append(el("option", { value: p.name, text: `${label} · ${p.step_count} steps · ${when}` }));
  }
  const asked = new URLSearchParams(location.search).get("protocol");  // the Check page links here by name
  if (asked && items.some((p) => p.name === asked)) select.value = asked;
  select.addEventListener("change", () => loadProtocol(select.value));
  loadProtocol(select.value);
}

async function openDeck() {
  const tab = window.open("", "_blank");
  $("deck-note").textContent = "Starting the visualizer…";
  try {
    const res = await fetch(`/api/healed/${encodeURIComponent(state.detail.name)}/deck`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || res.statusText);
    if (tab) tab.location.href = body.url; else window.open(body.url, "_blank");
    $("deck-note").textContent = `The deck on the STARlet now (nothing run) at ${body.url}`;
  } catch (err) {
    if (tab) tab.close();
    $("deck-note").textContent = `Could not open the visualizer: ${err.message}`;
  }
}

// ---------- Venus layout (.lay) ----------

function table(head, rows) {
  return el("div", { class: "table-wrap" }, el("table", { class: "bench-table lib-table" },
    el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows.map((cells) => el("tr", {}, ...cells.map((c) => el("td", {}, c)))))));
}

function badge(kind, text) { return el("span", { class: `badge ${kind}`, text }); }

function renderLayout() {
  const l = state.layout;
  $("layout-card").hidden = !l;
  if (!l) return;
  $("layout-title").textContent = `Venus layout: ${l.name}${l.library ? " (instrument library)" : ""}`;
  $("layout-meta").textContent = `${l.deck_file} · Venus ${l.venus_version || "?"} · ${l.items.length} items`;
  const cmp = l.comparison;
  if (cmp) {
    $("layout-verdict").replaceChildren(cmp.ok
      ? badge("ok", "matches")
      : badge("bad", "does not match"),
      ` The protocol's deck (${state.detail.deck_file}) is compared with ${l.name}.`);
  }
  if (cmp) {
    const status = { match: badge("ok", "match"), different: badge("bad", "different"), not_checked: badge("warn", "check by hand") };
    $("layout-compare").replaceChildren(table(["Protocol labware", "", "Simulated deck", "On the .lay"],
      cmp.items.map((i) => [i.id, status[i.status].cloneNode(true), i.expected || "",
        i.status === "match" ? `${i.venus_id}` : i.detail || ""])),
      cmp.extra.length ? el("p", { class: "muted", text: `Also on the .lay, not used by this protocol: ${cmp.extra.join(", ")}. Remove them or make sure they are out of the way.` }) : "");
  }
  $("layout-problems").replaceChildren(...(l.problems.length ? [
    el("h4", { text: `Not placeable in PyLabRobot (${l.problems.length})` }),
    table(["Item", "Problem", "What to do"], l.problems.map((p) => [p.id, p.problem, p.fix || ""])),
  ] : []));
  $("layout-positions").replaceChildren(
    el("h4", { text: "PyLabRobot positions and heights vs VENUS" }),
    table(["Item", "Point", "PyLabRobot (mm)", "VENUS (mm)", "Difference"], l.positions.map((p) => [
      p.id, p.what, p.plr.map(fmt).join(", "), p.lay.map(fmt).join(", "),
      p.ok ? badge("ok", "≤ 0.5 mm")
        : badge("bad", p.dz !== undefined ? `dz ${fmt(p.dz)}` : `dx ${fmt(p.dx)}, dy ${fmt(p.dy)}`)])));
}

async function uploadLayout() {
  const file = $("lay-file").files[0];
  if (!file) return;
  $("lay-note").textContent = `Reading ${file.name}…`;
  const query = new URLSearchParams({ filename: file.name, ...(state.detail ? { name: state.detail.name } : {}) });
  const res = await fetch(`/api/layouts?${query}`, { method: "POST", body: file });
  const reply = await res.json();
  if (!res.ok) { $("lay-note").textContent = reply.error || res.statusText; return; }
  state.layout = reply;
  state.layoutUploaded = true;
  $("lay-note").textContent = `${file.name} loaded; it replaces the instrument library's layout on this page.`;
  renderLayout();
  updateStart();
}

async function refreshLayout() {
  const res = await fetch(`/api/layouts/${state.layout.id}?name=${encodeURIComponent(state.detail.name)}`);
  if (!res.ok) { state.layout = null; $("lay-note").textContent = "The layout is no longer loaded on the server; load it again."; }
  else state.layout = await res.json();
  renderLayout();
}

// ---------- the Pi the STARlet is plugged into ----------

function renderRemote() {
  const r = state.remote;
  document.querySelectorAll(".pi-option").forEach((o) => { o.hidden = !r || !r.configured; });
  if (!r || !r.configured) return;
  let text;
  if (r.error) text = `${r.name} (${r.host}): ${r.error}`;
  else {
    const lock = r.lock.held_by ? `STARlet in use by pid ${r.lock.held_by}` : "STARlet free";
    text = `${r.name} (${r.host}) · PyLabRobot ${r.pylabrobot} · ${r.star_connected ? "STARlet on USB" : "no STARlet on USB"}`
      + ` · ${r.in_sync ? "code in sync" : "code out of date"} · ${lock}`;
  }
  $("pi-status").textContent = text;
  updateStart();
}

async function loadRemote(path = "/api/remote", options = {}) {
  $("pi-status").textContent = path.endsWith("sync") ? "Syncing pipeline/, config/ and healed/ to the Pi…" : "Checking the Pi…";
  $("pi-refresh").disabled = $("pi-sync").disabled = true;
  try {
    const res = await fetch(path, options);
    const reply = await res.json();
    if (!res.ok) throw new Error(reply.error || res.statusText);
    state.remote = reply;
  } catch (err) {
    state.remote = { ...(state.remote || { configured: true, name: "Pi", host: "?" }), error: err.message };
  }
  $("pi-refresh").disabled = $("pi-sync").disabled = false;
  renderRemote();
}

// ---------- execution ----------

function logLine(text, cls = "") {
  const li = el("li", { class: cls, text });
  $("run-log").prepend(li);
  return li;
}

function finishExecution() {
  clearInterval(state.timer);
  if (state.source) state.source.close();
  state.source = null;
  state.exId = null;
  $("abort").hidden = true;
  updateStart();
}

async function startExecution(event) {
  event.preventDefault();
  const { where, backend } = choice();
  const mode = document.querySelector("input[name=mode]:checked").value;
  const via = where === "pi" ? ` via ${state.remote.name} (${state.remote.host})` : "";
  if (backend === "star" && !confirm(`Run "${state.detail.protocol.protocol_name}" (${mode === "full" ? "full protocol" : "tip check"}) on the STARlet${via} now?`)) return;
  setStatus("running", "Starting", where === "pi" ? `Checking ${state.remote.host} and starting there…` : "Starting…");
  const res = await fetch("/api/executions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: state.detail.name, backend, mode, where, confirmed: [...state.checked],
      layout: state.layout ? state.layout.id : null }),
  });
  const reply = await res.json();
  if (!res.ok) { setStatus("bad", "Not started", reply.error || res.statusText); return; }
  state.exId = reply.execution_id;
  updateStart();
  $("abort").hidden = false;
  $("run-card").hidden = false;
  $("run-log").replaceChildren();
  $("progress-bar").style.width = "0%";
  $("run-title").textContent = `${mode === "full" ? "Full run" : "Tip check"} · ${backend === "star" ? "STARlet" : "ChatterBox rehearsal"}${where === "pi" ? ` on ${state.remote.host}` : ""}`;
  const started = Date.now();
  state.timer = setInterval(() => {
    const s = Math.floor((Date.now() - started) / 1000);
    $("elapsed").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 250);
  $("run-card").scrollIntoView({ behavior: "smooth" });

  const source = new EventSource(`/api/executions/${state.exId}/events`);
  state.source = source;
  const on = (kind, handler) => source.addEventListener(kind, (e) => handler(JSON.parse(e.data).data));
  on("status", (s) => { setStatus("running", "Running", s.message); logLine(s.message, "muted"); });
  on("step", (s) => {
    $("run-current").textContent = `Step ${s.step} of ${s.total}: ${s.description}`;
    $("run-meta").textContent = `${s.step - 1} of ${s.total} done`;
  });
  on("step_done", (s) => {
    $("progress-bar").style.width = `${(100 * s.step) / s.total}%`;
    $("run-meta").textContent = `${s.step} of ${s.total} done`;
    logLine(`✓ ${$("run-current").textContent.replace(/^Step /, "")} (${s.seconds} s)`);
  });
  on("done", (d) => {
    $("run-current").textContent = `Finished: ${d.steps} steps in ${d.seconds} s.`;
    setStatus("ok", "Done", `${d.mode === "full" ? "Protocol" : "Tip check"} finished in ${d.seconds} s.`);
  });
  on("aborted", (a) => {
    const tips = a.tips_mounted.length ? ` Tips are still mounted on channel(s) ${a.tips_mounted.join(", ")}; eject them from the instrument before the next run.` : "";
    $("run-current").textContent = `Aborted after step ${a.after_step} of ${a.total}.${tips}`;
    setStatus("bad", "Aborted", `Stopped after step ${a.after_step}.`);
  });
  on("error", (e) => {
    const where = e.step ? ` at step ${e.step} (${e.description})` : "";
    $("run-current").textContent = `Stopped${where}: ${e.message}`;
    logLine(`✕ ${e.message}`, "bad-text");
    setStatus("bad", "Error", `Stopped${where}.`);
  });
  source.addEventListener("end", finishExecution);
}

async function abortExecution() {
  if (!state.exId) return;
  $("abort").disabled = true;
  await fetch(`/api/executions/${state.exId}/abort`, { method: "POST" });
  logLine("Abort requested: stopping after the current step.", "muted");
  $("abort").disabled = false;
}

$("run-form").addEventListener("submit", startExecution);
$("abort").addEventListener("click", abortExecution);
async function replayProtocol() {
  if (!state.detail) return;
  const tab = window.open("", "_blank");
  $("deck-note").textContent = "Relaunching the 3D viewer and replaying the protocol…";
  try {
    const res = await fetch(`/api/healed/${encodeURIComponent(state.detail.name)}/replay`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || res.statusText);
    if (tab) tab.location.href = body.url; else window.open(body.url, "_blank");
    $("deck-note").textContent = `Replaying ${body.steps} steps in a new tab (about ${body.steps} s).`;
  } catch (err) {
    if (tab) tab.close();
    $("deck-note").textContent = `Could not replay: ${err.message}`;
  }
}

$("open-deck").addEventListener("click", openDeck);
$("replay").addEventListener("click", replayProtocol);
$("lay-file").addEventListener("change", uploadLayout);
$("pi-refresh").addEventListener("click", () => loadRemote());
$("pi-sync").addEventListener("click", () => loadRemote("/api/remote/sync", { method: "POST" }));
$("reset-checklist").addEventListener("click", () => { state.checked = new Set(); saveChecked(); renderChecklist(); });
document.querySelectorAll("input[name=backend]").forEach((r) => r.addEventListener("change", updateStart));
loadList();
loadRemote();
