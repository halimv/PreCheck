// Self-healing demo page: starts a run, renders its event stream as round cards,
// and opens PyLabRobot's visualizer for the passing protocol.

const STAGES = [["verify", "Verifier"], ["compile", "Compiler"], ["simulate", "Simulator"]];

const $ = (id) => document.getElementById(id);
const state = { protocols: [], runId: null, source: null, timer: null, startedAt: 0, rounds: {} };
// el, fmt, describeStep, volumes and renderEdit come from common.js.

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

function showProtocol(p) {
  $("protocol-card").hidden = false;
  $("protocol-name").textContent = p.name;
  $("protocol-steps").textContent = p.step_count;
  $("protocol-volumes").textContent = volumes(p.initial_volumes_ul);
}

async function loadSidebar() {
  state.protocols = await (await fetch("/api/protocols")).json();
  const select = $("protocol");
  for (const p of state.protocols) {
    select.append(el("option", { value: p.file, text: `${p.file} · ${p.step_count} steps` }));
  }
  const preferred = state.protocols.find((p) => p.file === "serial_dilution_v1.json");
  if (preferred) select.value = preferred.file;
  select.addEventListener("change", () => showProtocol(state.protocols.find((p) => p.file === select.value)));
  if (state.protocols.length) showProtocol(state.protocols.find((p) => p.file === select.value));

  const models = await (await fetch("/api/models")).json();
  const modelSelect = $("model");
  if (!models.available || !models.models.length) {
    modelSelect.append(el("option", { value: "qwen2.5-coder:7b", text: "qwen2.5-coder:7b" }));
    $("model-note").textContent = models.available
      ? "No models pulled yet. Run: ollama pull qwen2.5-coder:7b"
      : "Ollama isn't reachable on localhost:11434. Start it with `ollama serve`.";
  } else {
    for (const name of models.models) modelSelect.append(el("option", { value: name, text: name }));
    if (models.models.includes("qwen2.5-coder:7b")) modelSelect.value = "qwen2.5-coder:7b";
  }
}

// ---------- round cards ----------

function roundCard(round) {
  if (state.rounds[round]) return state.rounds[round];
  const title = round === 0 ? "Round 0 · original protocol" : `Round ${round}`;
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
  box.replaceChildren(...STAGES.map(([key, label], i) => {
    let cls = "stage";
    if (i < reached || (i === reached && gate.passed)) cls += " pass";
    else if (i === reached) cls += " fail";
    return el("span", { class: cls, text: label });
  }));
}

function onGate(gate) {
  const card = roundCard(gate.round);
  card.querySelector(".meta").textContent = `${gate.step_count} steps`;
  renderStages(card, gate);

  if (gate.passed) {
    card.append(el("div", { class: "block" },
      el("span", { class: "badge ok", text: "PASSED" }),
      document.createTextNode(gate.summary)));
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

function onModelRequest(req) {
  const card = roundCard(req.round);
  const block = el("div", { class: "block model" }, el("h4", { text: "Model" }),
    el("div", { class: "thinking" }, el("span", { class: "spinner", "aria-hidden": "true" }),
      el("span", { text: `Asking ${req.model} for a repair…` })));
  card.append(block);
  setStatus("running", "Running", `Round ${req.round}: waiting for ${req.model}`);
}

function onModelReply(reply) {
  const card = roundCard(reply.round);
  const block = card.querySelector(".block.model");
  const edits = reply.edits || [];
  block.replaceChildren(
    el("h4", { text: "Model's reasoning and proposed edits" }),
    el("p", { class: "reasoning", text: reply.reasoning || "(no reasoning given)" }),
    edits.length ? el("ul", { class: "edits" }, ...edits.map(renderEdit)) : el("p", { class: "muted", text: "No edits proposed." }),
  );
}

function onEdits(verdict) {
  const card = roundCard(verdict.round);
  if (verdict.accepted && verdict.errors && verdict.errors.length) {
    card.append(el("div", { class: "block verdict partial" },
      el("strong", { text: "Partly accepted by the harness. " }),
      el("span", { text: `Applied: ${verdict.description}. Protocol now has ${verdict.step_count} steps. Rejected, and sent back to the model:` }),
      el("ul", {}, ...verdict.errors.map((e) => el("li", { text: e })))));
  } else if (verdict.accepted) {
    card.append(el("div", { class: "block verdict ok" },
      el("strong", { text: "Accepted by the harness. " }),
      el("span", { text: `Protocol now has ${verdict.step_count} steps.` })));
  } else {
    card.append(el("div", { class: "block verdict bad" },
      el("strong", { text: "Rejected by the harness; the reason goes back to the model." }),
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
  // Open the tab inside the click so the browser doesn't block it, then point it at PLR's visualizer.
  const tab = window.open("", "_blank");
  if (tab) tab.document.write("<p style='font-family:sans-serif'>Starting PyLabRobot's visualizer…</p>");
  button.disabled = true;
  note.textContent = "Starting the visualizer…";
  try {
    const res = await fetch(`/api/runs/${state.runId}/visualize`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || res.statusText);
    if (tab) tab.location.href = body.url;
    else window.open(body.url, "_blank");
    note.textContent = `Replaying in PyLabRobot's visualizer at ${body.url}. Click again to restart the replay.`;
  } catch (err) {
    if (tab) tab.close();
    note.textContent = `Could not open the visualizer: ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

function onDone(done) {
  const healed = done.status === "HEALED";
  const passing = healed || done.status === "ALREADY_PASSING";
  const titles = {
    HEALED: `Healed after ${done.repair_rounds} repair round(s)`,
    ALREADY_PASSING: "Already passing: nothing to repair",
    GAVE_UP: `Gave up after ${done.repair_rounds} repair round(s)`,
  };
  const card = el("section", { class: "card result-card" },
    el("header", {}, el("h3", { text: titles[done.status] || done.status })));

  const body = el("div", { class: "block" });
  if (passing) {
    body.append(el("p", { text: `The protocol passes all three stages: ${done.step_count} steps, reagents loaded: ${volumes(done.initial_volumes_ul)}.` }));
  } else {
    body.append(el("p", { text: "No repair passed within the round limit. Nothing unverified was accepted; the original protocol is unchanged." }));
  }
  if (healed && done.diff) {
    body.append(el("h4", { text: "What changed (for review before use)" }), diffView(done.diff));
    if (done.saved_to) body.append(el("p", { class: "muted", text: `Saved to ${done.saved_to}/` }));
  }
  if (passing) {
    const note = el("span", { class: "hint" });
    const watch = el("button", { class: "primary", type: "button", text: "Watch in PyLabRobot's visualizer" });
    watch.addEventListener("click", () => openVisualizer(watch, note));
    const actions = el("div", { class: "actions" }, watch);
    if (healed) actions.append(el("a", { href: `/api/runs/${state.runId}/healed.json` },
      el("button", { type: "button", text: "Download healed protocol" })));
    actions.append(note);
    body.append(actions);
  }
  card.append(body);
  $("timeline").append(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });

  if (passing) setStatus("ok", healed ? "Healed" : "Passing", titles[done.status]);
  else setStatus("bad", "Gave up", titles[done.status]);
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

async function startRun(event) {
  event.preventDefault();
  $("start").disabled = true;
  $("empty").hidden = true;
  $("timeline").replaceChildren();
  state.rounds = {};
  setStatus("running", "Starting", "Starting the run…");

  const body = {
    protocol: $("protocol").value,
    model: $("model").value,
    feedback: document.querySelector("input[name=feedback]:checked").value,
    max_rounds: Number($("max-rounds").value) || 5,
  };
  const res = await fetch("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const reply = await res.json();
  if (!res.ok) {
    onError({ message: reply.error || res.statusText });
    $("start").disabled = false;
    return;
  }
  state.runId = reply.run_id;
  startTimer();

  const source = new EventSource(`/api/runs/${state.runId}/events`);
  state.source = source;
  const on = (kind, handler) => source.addEventListener(kind, (e) => handler(JSON.parse(e.data).data));
  on("start", (s) => setStatus("running", "Running", `${s.protocol_file}: ${s.step_count} steps, model ${s.model}`));
  on("gate", onGate);
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

$("run-form").addEventListener("submit", startRun);
loadSidebar();
