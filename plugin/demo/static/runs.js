// Runs page: every check PreCheck has made in this folder, with its summary, its provenance, and the review items a
// person acknowledges with a typed name. Read-only except for those acknowledgements.

const $ = (id) => document.getElementById(id);

const FILES = [
  ["summary.md", "Summary"], ["protocol.json", "Protocol (as checked)"], ["report.json", "Design review (data)"],
  ["heal_log.json", "Repair log"], ["script.py", "PyLabRobot script"], ["layout.yaml", "AHC layout"],
  ["input.txt", "Input"],
];

function badge(text, kind) { return el("span", { class: `badge ${kind}`, text }); }

function statusKind(run) { return run.passed ? "ok" : "bad"; }

function pretty(value) {
  return value === null || value === undefined ? "–" : String(value);
}

async function loadList() {
  const runs = await (await fetch("/api/runs")).json();
  const list = $("run-list");
  list.replaceChildren();
  if (!runs.length) {
    list.append(el("p", { class: "muted", text: "No runs yet. Check a protocol with `precheck --setup` and `precheck <protocol>` in this folder, or from the Check page." }));
    return;
  }
  for (const run of runs) {
    const must = (run.review?.items || []).filter((i) => i.severity === "must").length;
    const item = el("button", { type: "button", class: "run-item", "data-id": run.id },
      el("div", { class: "strong", text: run.protocol_name }),
      el("div", { class: "muted", text: `${new Date(run.created).toLocaleString()} · ${run.steps} steps · ${run.repair_rounds} repair round(s)` }),
      el("div", {}, badge(run.status, statusKind(run)), must ? badge(`${must} must review`, "warn") : null));
    item.addEventListener("click", () => { location.hash = run.id; });
    list.append(item);
  }
  highlight();
}

function highlight() {
  const current = location.hash.slice(1);
  document.querySelectorAll(".run-item").forEach((b) => b.classList.toggle("on", b.dataset.id === current));
}

function kv(rows) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of rows) dl.append(el("dt", { text: k }), el("dd", { text: pretty(v) }));
  return dl;
}

function provenanceView(p) {
  return el("details", {}, el("summary", { text: "Provenance: the files and versions this check depends on" }),
    kv(Object.entries(p).map(([k, v]) => [k.replace(/_/g, " "), v])));
}

function reviewView(run) {
  const items = run.review?.items || [];
  const acks = run.review?.acknowledged || {};
  if (!items.length) return el("p", { class: "muted", text: "Nothing needs a person's review." });
  return el("div", { class: "review" }, ...items.map((item, i) => {
    const ack = acks[String(i)];
    const box = el("div", { class: "review-item" },
      el("div", {}, badge(item.severity === "must" ? "must" : "check", item.severity === "must" ? "bad" : "warn"),
        el("span", { class: "strong", text: `  ${item.item}` })),
      el("p", { class: "muted", text: item.detail }));
    if (ack) {
      box.append(el("p", { text: `Acknowledged by ${ack.by} on ${new Date(ack.at).toLocaleString()}${ack.note ? `: ${ack.note}` : ""}` }));
    } else {
      const name = el("input", { type: "text", placeholder: "Your name", "aria-label": "Your name" });
      const note = el("input", { type: "text", placeholder: "Note (optional)", "aria-label": "Note" });
      const go = el("button", { type: "button", class: "small", text: "Acknowledge" });
      const msg = el("span", { class: "muted" });
      go.addEventListener("click", async () => {
        const res = await fetch(`/api/runs/${encodeURIComponent(run.id)}/acknowledge`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ item: i, name: name.value, note: note.value }),
        });
        const body = await res.json();
        if (!res.ok) { msg.textContent = body.error || res.statusText; return; }
        render(body);
      });
      box.append(el("div", { class: "actions" }, name, note, go, msg));
    }
    return box;
  }));
}

async function filesView(run) {
  const wrap = el("div", {});
  for (const [name, label] of FILES) {
    if (!run.files.some((f) => f === name || (name === "input.txt" && f.startsWith("input")))) continue;
    const target = name === "input.txt" ? run.files.find((f) => f.startsWith("input")) : name;
    const block = el("details", {}, el("summary", { text: label }));
    const text = el("pre", { class: "mono run-text", text: "loading…" });
    block.append(text);
    block.addEventListener("toggle", async () => {
      if (!block.open || text.dataset.loaded) return;
      const res = await fetch(`/api/runs/${encodeURIComponent(run.id)}/file/${encodeURIComponent(target)}`);
      text.textContent = res.ok ? await res.text() : "(not available)";
      text.dataset.loaded = "1";
    });
    wrap.append(block);
  }
  return wrap;
}

async function render(run) {
  $("status-chip").className = `chip ${run.passed ? "ok" : "bad"}`;
  $("status-chip").textContent = run.status;
  $("status-text").textContent = `${run.protocol_name} · checked ${new Date(run.created).toLocaleString()}`;
  const detail = $("run-detail");
  detail.replaceChildren(
    el("section", { class: "card" },
      el("header", {}, el("h3", { text: run.protocol_name }), el("span", { class: "meta", text: run.id })),
      el("div", { class: "block" },
        kv([
          ["Result", run.status], ["Steps", run.steps], ["Repair rounds", run.repair_rounds],
          ["Models tried", (run.models || []).map((m) => `${m.model} (${m.rounds} round(s), ${m.status})`).join("; ") || "none needed"],
          ["Simulated on", run.simulated_on],
        ]),
        provenanceView(run.provenance || {}),
      )),
    el("section", { class: "card" },
      el("header", {}, el("h3", { text: "Needs a person's review" })),
      el("div", { class: "block" }, reviewView(run))),
    el("section", { class: "card" },
      el("header", {}, el("h3", { text: "Files" })),
      el("div", { class: "block" }, await filesView(run))),
  );
}

async function show(id) {
  if (!id) return;
  const res = await fetch(`/api/runs/${encodeURIComponent(id)}`);
  if (!res.ok) { $("status-text").textContent = "That run is not in this folder."; return; }
  highlight();
  await render(await res.json());
}

window.addEventListener("hashchange", () => show(location.hash.slice(1)));
loadList().then(() => show(location.hash.slice(1)));
