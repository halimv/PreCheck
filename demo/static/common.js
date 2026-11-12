// Helpers shared by the live demo page (app.js) and the benchmark page (benchmark.js).
// All model and protocol text goes through textContent.

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) if (child != null) node.append(child);
  return node;
}

const fmt = (n) => (Number.isInteger(n) ? String(n) : String(+Number(n).toFixed(2)));

function channels(list = []) {
  if (!list.length) return "–";
  const contiguous = list.every((c, i) => i === 0 || c === list[i - 1] + 1);
  return contiguous && list.length > 1 ? `${list[0]}–${list[list.length - 1]}` : list.join(", ");
}

function describeStep(s) {
  if (s.action === "incubate" || s.action === "shake") {
    const parts = [s.action, s.labware, `${fmt(s.duration_s)} s`];
    if (s.speed_rpm != null) parts.push(`${fmt(s.speed_rpm)} rpm`);
    parts.push(s.temperature_c != null ? `${fmt(s.temperature_c)} °C` : "room temperature");
    return parts.join(" · ");
  }
  const parts = [s.action];
  if (s.volume_ul) parts.push(`${fmt(s.volume_ul)} µL`);
  parts.push(s.labware);
  if (s.column != null) parts.push(`column ${s.column}`);
  parts.push(`channel${(s.channels || []).length === 1 ? "" : "s"} ${channels(s.channels)}`);
  return parts.join(" · ");
}

function volumes(obj = {}) {
  const entries = Object.entries(obj);
  return entries.length ? entries.map(([k, v]) => `${k}: ${fmt(v)} µL`).join(", ") : "none listed";
}

// Knowledge-base template text with {placeholders} highlighted; {{ and }} are literal braces.
function template(text) {
  const span = el("span", {});
  for (const part of String(text).split(/(\{\{|\}\}|\{[^{}]+\})/)) {
    if (part === "{{") span.append("{");
    else if (part === "}}") span.append("}");
    else if (/^\{[^{}]+\}$/.test(part)) span.append(el("code", { class: "ph", text: part.slice(1, -1).split(":")[0] }));
    else if (part) span.append(part);
  }
  return span;
}

const PROPOSAL_KINDS = {
  add_fix: (p) => `Add a fix to ${p.target}`,
  replace_fixes: (p) => `Replace the fixes of ${p.target}`,
  new_entry: (p) => `New entry ${p.proposed.code || ""}`,
};

// A knowledge-base proposal. With `review`, pending proposals get Approve / Reject buttons that
// POST to the server and then call review(pid, result).
function proposalView(p, review) {
  const proposed = p.proposed || {};
  const status = p.status || (p.problems && p.problems.length ? "not kept" : "pending");
  const statusKind = { approved: "ok", rejected: "bad", pending: "running", "not kept": "bad" }[status] || "";
  const box = el("div", { class: "proposal" },
    el("div", { class: "proposal-head" },
      el("strong", { text: (PROPOSAL_KINDS[p.kind] || ((x) => x.kind))(p) }),
      el("span", { class: `chip ${statusKind}`, text: status }),
      p.id ? el("span", { class: "muted mono", text: p.id }) : null));
  const dl = el("dl", { class: "kv" });
  if (p.kind === "new_entry") {
    dl.append(el("dt", { text: "Title" }), el("dd", { text: proposed.title || "–" }),
      el("dt", { text: "Explanation" }), el("dd", {}, template(proposed.explanation || "–")),
      el("dt", { text: "Applies when" }), el("dd", { class: "mono", text: JSON.stringify(proposed.when || {}) }));
  }
  dl.append(el("dt", { text: "Fix" }), el("dd", {}, template(proposed.fix || "")),
    el("dt", { text: "Why" }), el("dd", { text: proposed.why || "–" }));
  if (proposed.fix_example && proposed.fix_example !== proposed.fix) {
    dl.append(el("dt", { text: "Filled in for this run" }), el("dd", { text: proposed.fix_example }));
  }
  if (proposed.fix_as_written && proposed.fix_as_written !== proposed.fix) {
    dl.append(el("dt", { text: "As written" }), el("dd", { class: "muted", text: proposed.fix_as_written }));
  }
  const ev = p.evidence || {};
  if (ev.round != null) {
    dl.append(el("dt", { text: "Evidence" }), el("dd", {
      text: `${p.protocol ? p.protocol + ", " : ""}round ${ev.round}, step ${ev.step}: the failure had repeated ${ev.repeats} time(s); `
        + `${(ev.edits_applied || []).length} edit(s) applied${p.problems && p.problems.length ? "" : " and the protocol then passed every stage"}.`,
    }));
  }
  if (p.warnings && p.warnings.length) {
    dl.append(el("dt", { text: "Check before approving" }), el("dd", {}, el("ul", { class: "spec-list" }, ...p.warnings.map((w) => el("li", { text: w })))));
  }
  if (p.problems && p.problems.length) dl.append(el("dt", { text: "Not kept" }), el("dd", { text: p.problems.join("; ") }));
  if (p.reviewed) dl.append(el("dt", { text: "Reviewed" }), el("dd", { text: `${p.reviewed.date}${p.reviewed.comment ? ": " + p.reviewed.comment : ""}` }));
  box.append(dl);

  if (review && status === "pending" && p.id) {
    const note = el("span", { class: "hint" });
    const act = async (decision, button) => {
      for (const b of box.querySelectorAll("button")) b.disabled = true;
      note.textContent = decision === "approve" ? "Adding it to the knowledge base…" : "Rejecting…";
      try {
        const res = await fetch(`/api/proposals/${encodeURIComponent(p.id)}/${decision}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        note.textContent = decision === "approve" ? `Approved: ${body.entry.id} updated. Future runs will see it.` : "Rejected. It stays on record.";
        review(p.id, body);
      } catch (err) {
        note.textContent = `Could not ${decision}: ${err.message}`;
        for (const b of box.querySelectorAll("button")) b.disabled = false;
      }
    };
    const approve = el("button", { type: "button", class: "primary", text: "Approve and add to knowledge base" });
    const reject = el("button", { type: "button", text: "Reject" });
    approve.addEventListener("click", () => act("approve", approve));
    reject.addEventListener("click", () => act("reject", reject));
    box.append(el("div", { class: "actions" }, approve, reject, note));
  }
  return box;
}

function renderEdit(edit) {
  if (edit.op === "set_initial_volume") {
    return el("li", { text: `Load ${fmt(edit.volume_ul)} µL into ${edit.labware} before the run` });
  }
  if (edit.op === "replace_step") {
    const steps = edit.new_steps || [];
    const head = steps.length ? `Replace step ${edit.step} with ${steps.length} step(s):` : `Delete step ${edit.step}`;
    return el("li", {}, el("span", { text: head }),
      steps.length ? el("ul", {}, ...steps.map((s) => el("li", { class: "mono", text: describeStep(s) }))) : null);
  }
  return el("li", { class: "mono", text: JSON.stringify(edit) });
}
