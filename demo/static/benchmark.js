// Benchmark page: pick a run from build/benchmark/, compare conditions, and open any run's rounds.

const CONDITION_ORDER = ["B0", "B1", "translated", "raw"];
const CONDITION_LABELS = { B0: "B0 · no repair", B1: "B1 · rule-based", translated: "LLM · lab-concept", raw: "LLM · raw error" };
const CHECKPOINTS = ["C1", "C2", "C3", "C4", "C5"];

const $ = (id) => document.getElementById(id);
const bench = { records: [], budget: 10, selected: null };

const label = (cond) => CONDITION_LABELS[cond] || cond;
const runLabel = (id) => id.replace(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/, "$1-$2-$3 $4:$5");

// The score a run would have had with `budget` repair rounds (B0 is only scored at 0).
function scoreAt(rec, budget) {
  const within = rec.scores.filter((s) => s.budget <= budget);
  return within.length ? within[within.length - 1] : rec.scores[0];
}

function scoreClass(score) {
  if (score >= 5) return "s-good";
  if (score >= 3) return "s-mid";
  return "s-bad";
}

function conditions() {
  const present = new Set(bench.records.map((r) => r.condition));
  return [...CONDITION_ORDER.filter((c) => present.has(c)), ...[...present].filter((c) => !CONDITION_ORDER.includes(c))];
}

function scenes() {
  return [...new Set(bench.records.map((r) => r.scene))];
}

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

// ---------- summary cards ----------

function renderSummary() {
  const cards = conditions().map((cond) => {
    const recs = bench.records.filter((r) => r.condition === cond);
    const scored = recs.map((r) => scoreAt(r, bench.budget));
    const healed = scored.filter((s) => s.healed).length;
    const labels = {};
    for (const s of scored) if (s.failure_label) labels[s.failure_label] = (labels[s.failure_label] || 0) + 1;
    const tokens = mean(recs.map((r) => r.prompt_tokens + r.output_tokens));
    return el("div", { class: "summary-card" },
      el("h3", { text: label(cond) }),
      el("div", { class: "big" }, el("span", { text: `${healed}/${recs.length}` }), el("small", { text: " healed" })),
      el("dl", { class: "kv" },
        el("dt", { text: "Mean score" }), el("dd", { text: mean(scored.map((s) => s.score)).toFixed(2) }),
        el("dt", { text: "Diagnosis" }), el("dd", { text: `${mean(scored.map((s) => s.diagnosis)).toFixed(2)} / 2` }),
        el("dt", { text: "Execution" }), el("dd", { text: `${mean(scored.map((s) => s.execution)).toFixed(2)} / 2` }),
        el("dt", { text: "Tokens / run" }), el("dd", { text: tokens ? Math.round(tokens).toLocaleString() : "–" }),
        el("dt", { text: "Time / run" }), el("dd", { text: `${Math.round(mean(recs.map((r) => r.wall_seconds)))} s` }),
      ),
      Object.keys(labels).length
        ? el("p", { class: "labels" }, ...Object.entries(labels).map(([k, v]) => el("span", { class: "badge", text: `${k} ${v}` })))
        : null,
    );
  });
  $("summary").replaceChildren(...cards);
}

// ---------- healed-by-budget table ----------

function budgets() {
  const all = new Set();
  for (const r of bench.records) for (const s of r.scores) if (s.budget > 0) all.add(s.budget);
  return [...all].sort((a, b) => a - b);
}

function renderCurve() {
  const bs = budgets();
  const head = el("tr", {}, el("th", { text: "Condition" }), ...bs.map((b) => el("th", { text: `${b} round${b === 1 ? "" : "s"}` })));
  const rows = conditions().map((cond) => {
    const recs = bench.records.filter((r) => r.condition === cond);
    return el("tr", {}, el("th", { text: label(cond) }), ...bs.map((b) => {
      const healed = recs.filter((r) => scoreAt(r, b).healed).length;
      return el("td", { class: b === bench.budget ? "current" : "", text: `${healed}/${recs.length}` });
    }));
  });
  $("curve").replaceChildren(el("thead", {}, head), el("tbody", {}, ...rows));
}

// ---------- scene x condition matrix ----------

function injectionText(rec) {
  const inj = rec.injection || {};
  if (inj.labware) return `${inj.labware} loaded at ${fmt(inj.initial_volume_ul)} µL`;
  return inj.note || "";
}

function renderMatrix() {
  const conds = conditions();
  const head = el("tr", {}, el("th", { text: "Scene" }), ...conds.map((c) => el("th", { text: label(c) })));
  const rows = scenes().map((scene) => {
    const first = bench.records.find((r) => r.scene === scene);
    const cells = conds.map((cond) => {
      const recs = bench.records.filter((r) => r.scene === scene && r.condition === cond);
      if (!recs.length) return el("td", { text: "–" });
      const s = scoreAt(recs[0], bench.budget);
      const status = s.healed ? `healed · round ${s.healed_round}` : (s.failure_label || recs[0].status);
      const button = el("button", { type: "button", class: `cell ${scoreClass(s.score)}` },
        el("span", { class: "cell-score", text: String(s.score) }),
        el("span", { class: "cell-status", text: status }));
      if (bench.selected === recs[0]) button.classList.add("selected");
      button.addEventListener("click", () => showDetail(recs[0]));
      return el("td", {}, button);
    });
    return el("tr", {}, el("th", {}, el("div", { text: scene }), el("small", { class: "muted", text: injectionText(first) })), ...cells);
  });
  $("matrix").replaceChildren(el("thead", {}, head), el("tbody", {}, ...rows));
}

// ---------- run detail ----------

function stageChips(round) {
  const order = ["verify", "compile", "simulate"];
  const names = { verify: "Verifier", compile: "Compiler", simulate: "Simulator" };
  const reached = order.indexOf(round.stage);
  return el("div", { class: "stages" }, ...order.map((key, i) => {
    let cls = "stage";
    if (i < reached || (i === reached && round.passed)) cls += " pass";
    else if (i === reached) cls += " fail";
    return el("span", { class: cls, text: names[key] });
  }));
}

function roundView(round, budget) {
  const beyond = round.round > budget;
  const title = round.round === 0 ? "Round 0 · injected protocol" : `Round ${round.round}`;
  const card = el("section", { class: `card${beyond ? " beyond" : ""}` },
    el("header", {}, el("h3", { text: title }), beyond ? el("span", { class: "meta", text: "beyond the selected budget" }) : null, stageChips(round)));

  card.append(el("div", { class: "block" },
    round.passed ? el("span", { class: "badge ok", text: "PASSED" }) : el("span", { class: "badge", text: "FAILED" }),
    document.createTextNode(round.result)));

  if ("model_reasoning" in round) {
    const edits = round.edits || [];
    const outOfBudget = !beyond && round.round >= budget;
    card.append(el("div", { class: `block model${outOfBudget ? " beyond" : ""}` },
      el("h4", { text: outOfBudget ? "Model's reply (after the budget ran out)" : "Model's reasoning and proposed edits" }),
      el("p", { class: "reasoning", text: round.model_reasoning || "(no reasoning given)" }),
      edits.length ? el("ul", { class: "edits" }, ...edits.map(renderEdit)) : el("p", { class: "muted", text: "No edits proposed." })));
    const applied = round.edits_applied;
    if (applied && applied.length && round.edit_errors && round.edit_errors.length) {
      card.append(el("div", { class: "block verdict partial" },
        el("strong", { text: `Partly accepted: edit${applied.length === 1 ? "" : "s"} ${applied.map((i) => i + 1).join(", ")} applied, the rest rejected.` }),
        el("ul", {}, ...round.edit_errors.map((e) => el("li", { text: e })))));
    } else if (round.edit_errors && round.edit_errors.length) {
      card.append(el("div", { class: "block verdict bad" },
        el("strong", { text: "Rejected by the harness." }),
        el("ul", {}, ...round.edit_errors.map((e) => el("li", { text: e })))));
    } else {
      card.append(el("div", { class: "block verdict ok" }, el("strong", { text: "Accepted by the harness." })));
    }
  }
  return card;
}

function showDetail(rec, scroll = true) {
  bench.selected = rec;
  renderMatrix();
  const s = scoreAt(rec, bench.budget);
  const pills = CHECKPOINTS.map((c) => el("span", { class: `pill ${s[c] ? "on" : "off"}`, text: `${c} ${s[c] ? "✓" : "✕"}` }));
  if (!s.healed) pills.push(el("span", { class: "pill penalty", text: "−1 not healed" }));

  const header = el("section", { class: "card result-card" },
    el("header", {}, el("h3", { text: `${rec.scene} · ${label(rec.condition)}` }),
      el("span", { class: `chip ${s.healed ? "ok" : "bad"}`, text: `score ${s.score}` })),
    el("div", { class: "block" },
      el("p", { text: injectionText(rec) }),
      el("div", { class: "pills" }, ...pills),
      el("dl", { class: "kv" },
        el("dt", { text: "Budget scored" }), el("dd", { text: `${s.budget} round(s)` }),
        el("dt", { text: "Outcome" }), el("dd", { text: s.healed ? `healed at round ${s.healed_round}` : (s.failure_label || rec.status) }),
        el("dt", { text: "Diagnosis / execution" }), el("dd", { text: `${s.diagnosis} / ${s.execution}` }),
        el("dt", { text: "Model" }), el("dd", { text: `${rec.model}${rec.temperature != null ? ` · temperature ${rec.temperature}` : ""}` }),
        el("dt", { text: "Feedback" }), el("dd", { text: rec.feedback }),
        el("dt", { text: "Tokens" }), el("dd", { text: (rec.prompt_tokens + rec.output_tokens).toLocaleString() }),
        el("dt", { text: "Wall time" }), el("dd", { text: `${rec.wall_seconds} s` }),
      ),
      rec.error ? el("p", { class: "verdict bad", text: `Run error: ${rec.error}` }) : null));

  const rounds = rec.rounds.map((r) => roundView(r, s.budget));
  $("detail").hidden = false;
  $("detail-body").replaceChildren(header, el("div", { class: "timeline" }, ...rounds));
  if (scroll) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- loading ----------

function renderAll() {
  renderSummary();
  renderCurve();
  renderMatrix();
  if (bench.selected) showDetail(bench.selected, false);
}

async function loadRun(id) {
  bench.records = await (await fetch(`/api/benchmarks/${encodeURIComponent(id)}`)).json();
  bench.selected = null;
  $("detail").hidden = true;
  const bs = budgets();
  const select = $("budget");
  select.replaceChildren(...bs.map((b) => el("option", { value: String(b), text: `${b} round${b === 1 ? "" : "s"}` })));
  bench.budget = bs.length ? bs[bs.length - 1] : 0;
  select.value = String(bench.budget);
  $("bench-chip").className = "chip ok";
  $("bench-chip").textContent = runLabel(id);
  const first = bench.records.find((r) => r.model && r.model !== "rule-based");
  $("bench-text").textContent = `${bench.records.length} runs · ${scenes().length} scenes · ${conditions().length} conditions`
    + (first ? ` · ${first.model}, temperature ${first.temperature}` : "");
  renderAll();
}

async function init() {
  const runs = await (await fetch("/api/benchmarks")).json();
  const select = $("bench");
  if (!runs.length) {
    $("bench-note").textContent = "No results in build/benchmark/ yet.";
    return;
  }
  select.replaceChildren(...runs.map((r) => el("option", { value: r.id, text: `${runLabel(r.id)} · ${r.runs} runs` })));
  select.addEventListener("change", () => loadRun(select.value));
  $("budget").addEventListener("change", () => {
    bench.budget = Number($("budget").value);
    renderAll();
  });
  await loadRun(runs[0].id);
}

init();
