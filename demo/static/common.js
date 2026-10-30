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
