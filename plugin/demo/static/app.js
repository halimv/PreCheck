// The Check page: takes a protocol (text, a file, or a saved IR), starts a run, renders its event stream as
// cards (draft, repair rounds, result with the design review), opens the 3D viewer for the passing protocol,
// and sends a change the scientist asks for back through the same loop.

const STAGES = [  // the verifier is out of the loop for now
  ["compile", "Compile", "The plan is turned into PyLabRobot code. A step that cannot be written as code fails here."],
  ["simulate", "Simulate", "The code runs on a model of the instrument with tip and volume tracking. Nothing is sent to the robot."],
];

const $ = (id) => document.getElementById(id);
const state = { protocols: [], runId: null, source: null, timer: null, startedAt: 0, rounds: {}, tab: "text" };
// el, fmt, describeStep, volumes, renderEdit, info and table come from common.js.

// ---------- status bar ----------

function setStatus(kind, label, text) {
  const chip = $("status-chip");
  chip.className = `chip ${kind}`;
  chip.textContent = label;
  $("status-text").textContent = text;
}

function startTimer() {
  state.startedAt = Date.now();
  clearInterval(state.timer);
  state.timer = setInterval(() => {
    const s = Math.floor((Date.now() - state.startedAt) / 1000);
    $("elapsed").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 250);
}

// ---------- sidebar ----------

function showTab(tab) {
  state.tab = tab;
  for (const name of ["text", "saved"]) {
    $(`tab-${name}`).classList.toggle("active", name === tab);
    $(`tab-${name}`).setAttribute("aria-selected", String(name === tab));
  }
  $("source-text").hidden = tab !== "text";
  $("source-saved").hidden = tab !== "saved";
}

function showProtocol(p) {
  $("protocol-info").textContent = p ? `${p.name} · ${p.step_count} steps · loaded: ${volumes(p.initial_volumes_ul)}` : "";
}

async function loadSidebar() {
  $("tab-text").addEventListener("click", () => showTab("text"));
  $("tab-saved").addEventListener("click", () => showTab("saved"));
  $("file").addEventListener("change", () => {
    const file = $("file").files[0];
    $("file-name").textContent = file ? `${file.name} (click to change)` : "Attach a PDF or text file";
  });

  state.protocols = await (await fetch("/api/protocols")).json();
  const select = $("protocol");
  for (const p of state.protocols) select.append(el("option", { value: p.file, text: p.file }));
  const current = () => state.protocols.find((p) => p.file === select.value);
  select.addEventListener("change", () => showProtocol(current()));
  showProtocol(current());

  const models = await (await fetch("/api/models")).json();
  const modelSelect = $("model");
  const group = (label, healer, names) => el("optgroup", { label },
    ...names.map((name) => el("option", { value: `${healer}:${name}`, text: name })));
  modelSelect.append(group("Claude", "claude", models.claude.models));
  if (models.ollama.models.length) modelSelect.append(group("Local (Ollama)", "ollama", models.ollama.models));
  modelSelect.value = `claude:${models.claude.default}`;
  if (!models.claude.available) {
    $("model-note").textContent = models.ollama.available
      ? "The Claude CLI isn't installed: choose a local model. Describing a protocol needs Claude."
      : "The Claude CLI isn't installed and Ollama isn't running: install one to repair protocols.";
    if (models.ollama.available) modelSelect.value = `ollama:${models.ollama.models[0]}`;
  }
}

// ---------- the draft ----------

function onDraftRequest(req) {
  const card = el("section", { class: "card", id: "draft-card" },
    el("header", {}, el("h3", { text: req.note ? "Revision" : "Draft" })),
    el("div", { class: "block" },
      req.note ? el("p", { class: "reasoning", text: req.note }) : null,
      el("div", { class: "thinking" }, el("span", { class: "spinner", "aria-hidden": "true" }), el("span", { text: `${req.what}…` }))));
  $("timeline").append(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });
  setStatus("running", "Drafting", `${req.what}. This takes a minute or two.`);
}

function onDraft(d) {
  const card = document.querySelector("#draft-card:last-of-type") || $("draft-card");
  card.removeAttribute("id");
  card.querySelector(".thinking").remove();
  card.querySelector("header").append(el("span", { class: "meta", text: `${d.protocol_name} · ${d.step_count} steps` }));
  const block = card.querySelector(".block");
  block.append(el("h4", {}, "Labware chosen", info("Each item the protocol needs, matched to real labware in VENUS's library and placed on the deck that is on the STARlet.")),
    table(["Name", "Labware", "Where", ""], d.labware.map((l) => [l.name, l.type, l.where, l.action])));
  if (d.operator_changes.length) {
    block.append(el("h4", { class: "lib-h4" }, "To place before the run"), el("ul", { class: "fixes" }, ...d.operator_changes.map((c) => el("li", { text: c }))));
  }
  if (d.assumptions.length) {
    block.append(el("details", {}, el("summary", { text: `${d.assumptions.length} assumptions Claude made` }),
      el("ul", { class: "fixes" }, ...d.assumptions.map((a) => el("li", { text: a })))));
  }
}

// ---------- round cards ----------

function roundCard(round) {
  if (state.rounds[round]) return state.rounds[round];
  const title = round === 0 ? "First check" : `Repair ${round}`;
  const header = el("header", {}, el("h3", { text: title }), el("span", { class: "meta" }), el("div", { class: "stages" }));
  const card = el("section", { class: "card" }, header);
  $("timeline").append(card);
  state.rounds[round] = card;
  card.scrollIntoView({ behavior: "smooth", block: "end" });
  return card;
}

function renderStages(card, gate) {
  const reached = STAGES.findIndex(([key]) => key === gate.stage);
  const box = card.querySelector(".stages");
  box.replaceChildren(...STAGES.map(([key, label, tip], i) => {
    let cls = "stage";
    if (i < reached || (i === reached && gate.passed)) cls += " pass";
    else if (i === reached) cls += " fail";
    return el("span", { class: cls, text: label, "data-tip": tip });
  }));
}

function onGate(gate) {
  const card = roundCard(gate.round);
  card.querySelector(".meta").textContent = `${gate.step_count} steps`;
  renderStages(card, gate);

  if (gate.passed) {
    card.append(el("div", { class: "block" },
      el("span", { class: "badge ok", text: "PASSED", "data-tip": gate.summary }),
      document.createTextNode("Every step ran.")));
    return;
  }

  const block = el("div", { class: "block" }, el("h4", { text: `Failure at stage: ${gate.stage}` }));
  const code = gate.error_code || gate.stage.toUpperCase();
  const where = gate.step != null ? `step ${gate.step}` : "";
  block.append(el("p", {}, el("span", { class: "badge", text: code }), el("span", { class: "strong", text: where })));
  block.append(el("p", { text: gate.explanation || gate.summary }));
  if (gate.suggested_fixes && gate.suggested_fixes.length) {
    block.append(el("ul", { class: "fixes" }, ...gate.suggested_fixes.map((f) => el("li", { text: f }))));
  }
  if (gate.raw_error) {
    block.append(el("details", {}, el("summary", { text: "Raw PyLabRobot error" }), el("pre", { text: gate.raw_error })));
  }
  card.append(block);
  setStatus("running", "Running", `Round ${gate.round}: ${code}${where ? " at " + where : ""}`);
}

function onEscalate(e) {
  const card = roundCard(e.round);
  card.append(el("div", { class: "block verdict partial" },
    el("strong", { text: "Same failure again. " }),
    el("span", { text: `${e.code} at step ${e.step} has come back ${e.repeats} time(s) in a row, so the model is asked to reason past the knowledge base's suggestions and propose a change to it.` })));
  setStatus("running", "Running", `Round ${e.round}: escalating ${e.code}`);
}

function onModelRequest(req) {
  const card = roundCard(req.round);
  const block = el("div", { class: "block model" }, el("h4", { text: "Model" }),
    el("div", { class: "thinking" }, el("span", { class: "spinner", "aria-hidden": "true" }),
      el("span", { text: `Asking ${req.model} for a repair…` })));
  card.append(block);
  setStatus("running", "Repairing", `Repair ${req.round + 1}: waiting for ${req.model}`);
}

function onModelReply(reply) {
  const card = roundCard(reply.round);
  const block = card.querySelector(".block.model");
  const edits = reply.edits || [];
  block.replaceChildren(
    el("h4", {}, "Proposed repair", info("The model's reasoning and its edits to the plan. The harness applies only edits that fix the failing step without changing how much liquid moves.")),
    el("p", { class: "reasoning", text: reply.reasoning || "(no reasoning given)" }),
    edits.length ? el("ul", { class: "edits" }, ...edits.map(renderEdit)) : el("p", { class: "muted", text: "No edits proposed." }),
  );
  if (reply.knowledge_proposal) {
    const p = reply.knowledge_proposal;
    block.append(el("h4", { class: "lib-h4", text: "Proposed change to the knowledge base (kept only if this fix works)" }),
      el("dl", { class: "kv" },
        el("dt", { text: "Kind" }), el("dd", { text: p.kind }),
        el("dt", { text: "Fix" }), el("dd", { text: p.fix || "" }),
        el("dt", { text: "Why" }), el("dd", { text: p.why || "" })));
  }
}

function onEdits(verdict) {
  const card = roundCard(verdict.round);
  if (verdict.accepted && verdict.errors && verdict.errors.length) {
    card.append(el("div", { class: "block verdict partial" },
      el("strong", { text: "Partly accepted. " }),
      el("span", { text: `Applied: ${verdict.description}. Rejected:` }),
      el("ul", {}, ...verdict.errors.map((e) => el("li", { text: e })))));
  } else if (verdict.accepted) {
    card.append(el("div", { class: "block verdict ok" },
      el("strong", { text: "Accepted. " }),
      el("span", { text: `${verdict.step_count} steps now.` })));
  } else {
    card.append(el("div", { class: "block verdict bad" },
      el("strong", { text: "Rejected. ", "data-tip": "The reasons go back to the model for its next attempt." }),
      el("ul", {}, ...verdict.errors.map((e) => el("li", { text: e })))));
  }
}

// ---------- result ----------

function diffView(text) {
  const pre = el("pre", { class: "diff" });
  for (const line of text.split("\n")) {
    let cls = "";
    if (line.startsWith("@@")) cls = "hunk";
    else if (line.startsWith("+") && !line.startsWith("+++")) cls = "add";
    else if (line.startsWith("-") && !line.startsWith("---")) cls = "del";
    pre.append(el("span", { class: cls, text: line + "\n" }));
  }
  return pre;
}

async function openVisualizer(button, note) {
  // Open the tab inside the click so the browser doesn't block it, then point it at PLR's viewer.
  const tab = window.open("", "_blank");
  if (tab) tab.document.write("<p style='font-family:sans-serif'>Starting the 3D viewer…</p>");
  button.disabled = true;
  note.textContent = "Starting the 3D viewer…";
  try {
    const res = await fetch(`/api/runs/${button.dataset.run}/visualize`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || res.statusText);
    if (tab) tab.location.href = body.url;
    else window.open(body.url, "_blank");
    note.textContent = "Replaying in a new tab.";
  } catch (err) {
    if (tab) tab.close();
    note.textContent = `Could not open the viewer: ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

function contents(w) {
  const parts = Object.entries(w.contents).map(([name, c]) =>
    `${name.length > 34 ? name.slice(0, 33) + "…" : name} ${c.ul < 1 ? Number(c.ul).toLocaleString(undefined, { maximumSignificantDigits: 2 }) : fmt(c.ul)} µL${c.dilution >= 2 ? ` (1:${Number(c.dilution).toLocaleString()})` : ""}`);
  const cell = el("span", { text: parts.join(" + ") || "empty" });
  if (w.flags.length) cell.append(el("span", { class: "flag", text: `  ${w.flags.join("; ")}` }));
  return cell;
}

function reviewBlock(report) {
  const r = report.review;
  const block = el("div", { class: "block" });
  const wells = el("div", {},
    el("h4", {}, "What each well ends up holding", info("Traced through every step. The ratio is the dilution of that reagent in the well. A red note marks a well outside its limits.")),
    table(["Plate", "Column", "Rows", "µL", "Contents"], r.wells.map((w) => [w.plate, w.column, w.rows.length === 8 ? "A–H" : w.rows,
      Array.isArray(w.volume_ul) ? `${fmt(w.volume_ul[0])}–${fmt(w.volume_ul[1])}` : w.volume_ul, contents(w)])));
  const reagents = el("div", {},
    el("h4", {}, "Reagents to load", info("Load: what goes in before the run. Drawn: what the plan takes out. Left: what stays behind as dead volume.")),
    table(["Container", "Load µL", "Drawn", "Left", "Holds up to"], r.reagents.map((g) => [el("span", { text: g.labware, "data-tip": g.reagent }), g.loaded_ul, g.drawn_ul, g.left_ul, g.capacity_ul])));
  const limits = Object.entries(r.limits).map(([plate, rule]) => `${plate}: ${fmt(rule.min_ul)}–${fmt(rule.max_ul)} µL per well`);
  const tips = Object.entries(r.tips.columns).map(([rack, cols]) => (cols.length ? `${rack} columns ${cols[0]}–${cols[cols.length - 1]}` : rack));
  reagents.append(el("p", { class: "hint" },
    `Tips: ${r.tips.used} (${tips.join("; ")}).`,
    limits.length ? ` Usable volume: ${limits.join("; ")}.` : "",
    r.policy ? info(`From config/precheck_policy.json: ${fmt(r.policy.dead_volume_ul)} µL dead volume per well, filled to at most ${Math.round(r.policy.max_fill_fraction * 100)}%.`) : null));
  block.append(el("div", { class: "review-grid" }, wells, reagents));
  return block;
}

function improveBlock(report, runId) {
  const hints = report.suggestions;
  const block = el("div", { class: "block" },
    el("h4", {}, "Improve it", info("Suggestions are improvements, not errors: the protocol already passes. Tick any, or describe a change in your own words. The change goes back through draft, check and repair, and is saved as the next version.")));
  const boxes = [];
  if (hints.length) {
    block.append(el("ul", { class: "suggestions" }, ...hints.map((h) => {
      const box = el("input", { type: "checkbox" });
      boxes.push([box, h]);
      return el("li", {}, el("label", { "data-tip": h.detail }, box, el("span", { text: h.title })));
    })));
  }
  const text = el("textarea", { rows: "2", placeholder: "e.g. use 3 replicate rows instead of 8", "aria-label": "Change to make" });
  const go = el("button", { type: "button", class: "primary", text: "Revise" });
  const note = el("span", { class: "hint" });
  go.addEventListener("click", async () => {
    const asked = [...boxes.filter(([b]) => b.checked).map(([, h]) => h.request), text.value.trim()].filter(Boolean).join(" ");
    if (!asked) { note.textContent = "Tick a suggestion or describe a change."; return; }
    go.disabled = true;
    const res = await fetch(`/api/runs/${runId}/revise`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: asked }) });
    const reply = await res.json();
    if (!res.ok) { note.textContent = reply.error || res.statusText; go.disabled = false; return; }
    note.textContent = "Sent: the next version is below.";
    follow(reply.run_id);
  });
  block.append(el("div", { class: "revise" }, text, go), note);
  return block;
}

function handOffBlock(report) {
  const ahc = report.ahc;
  const block = el("div", { class: "block" },
    el("h4", {}, "Run it", info("Precheck can run this itself from the Execute page: a deck checklist, a rehearsal, then the STARlet. AHC is optional: it adds a supervised run with error recovery and an on-site check that the deck matches these files.")));
  const files = report.files;
  block.append(el("p", {}, el("span", { class: "mono", text: files.ir }), el("span", { class: "muted", text: "  saved with its script, log and report" })));
  const line = el("p", {});
  if (ahc.not_on_layout.length) {
    line.append(el("span", { class: "flag", text: `AHC layout is missing ${ahc.not_on_layout.length} item(s). `, "data-tip": ahc.not_on_layout.join(" · ") }));
  } else {
    line.append(el("span", { class: "ok-text", text: "AHC layout: the whole deck is on it. " }));
  }
  line.append(el("span", { class: "mono", text: files.ahc_layout }));
  block.append(line);
  if (ahc.differs_from_venus.length) {
    block.append(el("details", {}, el("summary", { text: `${ahc.differs_from_venus.length} place(s) where AHC's labware model differs from VENUS` }),
      el("ul", { class: "fixes" }, ...ahc.differs_from_venus.map((w) => el("li", { text: w })))));
  }
  return block;
}

function onDone(done) {
  const healed = done.status === "HEALED";
  const passing = healed || done.status === "ALREADY_PASSING";
  const titles = {
    HEALED: `Ready after ${done.repair_rounds} repair${done.repair_rounds === 1 ? "" : "s"}`,
    ALREADY_PASSING: "Ready: nothing to repair",
    GAVE_UP: `Not ready after ${done.repair_rounds} repairs`,
  };
  const runId = state.runId;
  const card = el("section", { class: "card result-card" },
    el("header", {}, el("h3", { text: titles[done.status] || done.status }),
      el("span", { class: "meta", text: passing ? `${done.step_count} steps · checked on ${done.report.simulated_on}` : "" })));

  if (passing) {
    const note = el("span", { class: "hint" });
    const watch = el("button", { class: "primary", type: "button", text: "Watch in 3D", "data-run": runId,
      "data-tip": "Replays the whole assay in PyLabRobot's 3D viewer, in a new tab." });
    watch.addEventListener("click", () => openVisualizer(watch, note));
    const run = el("a", { href: `/execute?protocol=${encodeURIComponent(done.report.name)}` },
      el("button", { type: "button", text: "Set up and run", "data-tip": "Opens the Execute page: deck checklist, rehearsal, then the STARlet." }));
    const download = el("a", { href: `/api/runs/${runId}/healed.json` },
      el("button", { type: "button", text: "Download", "data-tip": "The passing protocol as JSON." }));
    card.append(el("div", { class: "block" }, el("div", { class: "actions", style: "margin-top:0" }, watch, run, download, note)));
    card.append(reviewBlock(done.report), improveBlock(done.report, runId), handOffBlock(done.report));
    const changes = [["Repairs made", done.diff], ["Changes from the previous version", done.revision_diff]].filter(([, d]) => d);
    if (changes.length) {
      card.append(el("div", { class: "block" }, ...changes.map(([label, diff]) =>
        el("details", {}, el("summary", { text: label }), diffView(diff)))));
    }
  } else {
    card.append(el("div", { class: "block" }, el("p", { text: "No repair passed within the limit. Nothing unverified was accepted. Change the description, or allow more repair rounds, and check again." })));
  }
  const pending = done.proposals || [];
  const notKept = done.proposals_not_kept || [];
  if (pending.length || notKept.length) {
    const block = el("div", { class: "block" }, el("h4", {}, "Knowledge-base proposals",
      info("The model's fix worked. Approving adds its proposal to knowledge/diagnostics.json, so future runs get this suggestion. You can also review it later on the Library page.")));
    for (const p of [...pending, ...notKept]) block.append(proposalView(p, () => {}));
    card.append(block);
  }
  $("timeline").append(card);
  card.scrollIntoView({ behavior: "smooth", block: "start" });

  if (passing) setStatus("ok", "Ready", titles[done.status]);
  else setStatus("bad", "Not ready", titles[done.status]);
}

function onError(err) {
  $("timeline").append(el("section", { class: "card" },
    el("div", { class: "block verdict bad" }, el("strong", { text: "Run stopped: " }), el("span", { text: err.message }))));
  setStatus("bad", "Error", err.message);
}

// ---------- run lifecycle ----------

function finishRun() {
  clearInterval(state.timer);
  if (state.source) state.source.close();
  state.source = null;
  $("start").disabled = false;
}

// Follow a run's events. A revision is a new run that continues the same timeline.
function follow(runId) {
  if (state.source) state.source.close();
  state.runId = runId;
  state.rounds = {};
  $("start").disabled = true;
  startTimer();
  const source = new EventSource(`/api/runs/${runId}/events`);
  state.source = source;
  const on = (kind, handler) => source.addEventListener(kind, (e) => handler(JSON.parse(e.data).data));
  on("draft_request", onDraftRequest);
  on("draft", onDraft);
  on("start", (s) => setStatus("running", "Checking", `${s.protocol_name}: ${s.step_count} steps on ${s.simulated_on}, repairs by ${s.model}`));
  on("gate", onGate);
  on("escalate", onEscalate);
  on("model_request", onModelRequest);
  on("model_reply", onModelReply);
  on("edits", onEdits);
  on("done", onDone);
  on("run_error", onError);
  source.addEventListener("end", finishRun);
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) finishRun();
  };
}

async function startRun(event) {
  event.preventDefault();
  const form = new FormData();
  const [healer, ...model] = $("model").value.split(":");
  form.set("healer", healer);
  form.set("model", model.join(":"));
  form.set("feedback", $("feedback").value);
  form.set("max_rounds", String(Number($("max-rounds").value) || 5));
  form.set("escalate", String($("escalate").checked));
  if (state.tab === "saved") form.set("protocol", $("protocol").value);
  else if ($("file").files[0]) form.set("file", $("file").files[0]);
  else form.set("text", $("text").value);

  $("start").disabled = true;
  $("empty").hidden = true;
  $("timeline").replaceChildren();
  setStatus("running", "Starting", "Starting…");
  const res = await fetch("/api/runs", { method: "POST", body: form });
  const reply = await res.json();
  if (!res.ok) {
    onError({ message: reply.error || res.statusText });
    $("start").disabled = false;
    return;
  }
  follow(reply.run_id);
}

$("run-form").addEventListener("submit", startRun);
loadSidebar();
