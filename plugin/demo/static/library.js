// Library page: ground truth only. VENUS's labware library and the deck on the STARlet now, on one tab; the
// diagnostics knowledge base (and what runs recorded in it) on the other. Read-only.

const $ = (id) => document.getElementById(id);
const lib = { data: null, tab: "labware" };

const CATEGORY_LABELS = { plates: "Plates", tips: "Tips", reagent_containers: "Reagent containers", tip_racks: "Tip racks" };
const humanize = (key) => key.replace(/_/g, " ");
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// ---------- shared ----------

function card(searchText, ...children) {
  const node = el("section", { class: "card lib-card" }, ...children);
  node.dataset.search = searchText.toLowerCase();
  return node;
}

function group(title, subtitle, cards) {
  return el("section", { class: "bench-section lib-group" },
    el("h2", { text: title }),
    subtitle ? el("p", { class: "muted lib-sub", text: subtitle }) : null,
    el("div", { class: "lib-list" }, ...cards));
}

function chip(text, kind = "") {
  return el("span", { class: `chip ${kind}`, text });
}

// Nested specification objects as a definition list; arrays of plain values as a comma list.
function specView(value) {
  if (Array.isArray(value)) {
    if (value.every((v) => typeof v !== "object")) return document.createTextNode(value.join(", "));
    return el("ul", { class: "spec-list" }, ...value.map((v) => el("li", {}, specView(v))));
  }
  if (value && typeof value === "object") {
    const dl = el("dl", { class: "kv" });
    for (const [k, v] of Object.entries(value)) dl.append(el("dt", { text: humanize(k) }), el("dd", {}, specView(v)));
    return dl;
  }
  return document.createTextNode(String(value));
}

// ---------- labware tab ----------

// Labware is keyed by its VENUS type; a deck places one of those types under its own id (STF_L_0001 is an STF_L).
const venusType = (spec) => spec.venus_type || spec.factory;
const placedTypes = (decks) => new Set(decks.flatMap((d) => Object.values(d.labware).map(venusType)));

function inventoryIndex(inventory) {
  const index = {};
  for (const [category, items] of Object.entries(inventory)) {
    if (category === "labware_library") continue;
    for (const id of Object.keys(items)) index[id] = category;
  }
  return index;
}

function keyFacts(category, item) {
  const facts = [];
  if (category === "plates") {
    facts.push(["Format", item.well_format], ["Capacity", item.capacity_ul_per_well != null ? `${fmt(item.capacity_ul_per_well)} µL per well` : null]);
  } else if (category === "tips") {
    const s = item.specifications || {};
    facts.push(["Type", item.tip_type], ["Tip volume", s.capacity_ul != null ? `${fmt(s.capacity_ul)} µL` : null],
      ["Filter", s.filter ? "yes" : null]);
  } else {
    facts.push(["Type", item.type], ["Holds", item.volume_ul != null ? `${fmt(item.volume_ul)} µL` : null]);
  }
  return facts.filter(([, v]) => v != null && v !== "");
}

function inventoryCard(category, item, decks) {
  const onDecks = decks.filter((d) => Object.values(d.labware).some((s) => venusType(s) === item.id)).map((d) => d.file);
  const title = item.product_name || item.type || item.id;
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of keyFacts(category, item)) dl.append(el("dt", { text: k }), el("dd", { text: String(v) }));
  const rest = Object.fromEntries(Object.entries(item).filter(([k]) => k !== "id"));
  return card(`${item.id} ${title} ${item.description || ""}`,
    el("header", {},
      el("div", {}, el("h3", { class: "mono", text: item.id }), el("div", { class: "muted lib-title", text: title })),
      el("div", { class: "lib-chips" }, onDecks.length
        ? chip(`on ${onDecks.join(", ")}`, "ok")
        : chip("not placed on any deck"))),
    el("div", { class: "block" },
      item.description ? el("p", { text: item.description }) : null,
      dl,
      el("details", {}, el("summary", { text: "All specifications" }), specView(rest))));
}

function placement(spec, deck) {
  if (spec.kind === "trash") return "deck trash";
  if (spec.on) return `on ${spec.on} (${deck.machines?.[spec.on]?.kind?.replace(/_/g, "-") || "machine"})`;
  if (spec.carrier) return `${spec.carrier} · slot ${spec.slot}`;
  return "–";
}

function deckCard(deck, index) {
  const rows = Object.entries(deck.labware).map(([id, spec]) => {
    const known = venusType(spec) in index;
    const status = spec.kind === "trash" ? el("span", { class: "muted", text: "n/a" })
      : known ? el("span", { class: "badge ok", text: CATEGORY_LABELS[index[venusType(spec)]] || index[venusType(spec)] })
        : el("span", { class: "badge warn", text: "not in VENUS's library" });
    return el("tr", {},
      el("th", { class: "mono", text: id }),
      el("td", { text: humanize(spec.kind) }),
      el("td", { class: "mono", text: spec.factory || "–" }),
      el("td", { text: placement(spec, deck) }),
      el("td", {}, status),
      el("td", { class: "muted", text: spec.note || "" }));
  });
  const machines = Object.entries(deck.machines || {}).map(([id, m]) => el("tr", {},
    el("th", { class: "mono", text: id }),
    el("td", { text: humanize(m.kind) }),
    el("td", { text: `rails ${m.rails}` }),
    el("td", { text: [m.speed_rpm ? `${m.speed_rpm[0]}–${m.speed_rpm[1]} rpm` : null, m.max_temperature_c ? `up to ${m.max_temperature_c} °C` : null].filter(Boolean).join(" · ") }),
    el("td", { class: "muted", text: m.note || "" })));
  const carriers = (deck.carriers || []).map((c) => `${c.name} (${c.factory}, rails ${c.rails})`).join(" · ");
  return card(`${deck.file} ${Object.keys(deck.labware).join(" ")} ${deck.used_by.join(" ")}`,
    el("header", {},
      el("div", {}, el("h3", { class: "mono", text: deck.file }), el("div", { class: "muted lib-title", text: `${deck.deck || ""} · PyLabRobot ${deck.plr_version || ""}` })),
      el("div", { class: "lib-chips" }, deck.used_by.length ? chip(plural(deck.used_by.length, "protocol"), "ok") : chip("no protocol uses it"))),
    el("div", { class: "block" },
      deck.description ? el("p", { class: "muted", text: deck.description }) : null,
      deck.used_by.length ? el("p", {}, el("span", { class: "strong", text: "Used by: " }), el("span", { class: "mono", text: deck.used_by.join(", ") })) : null,
      el("div", { class: "table-wrap" }, el("table", { class: "bench-table lib-table" },
        el("thead", {}, el("tr", {}, ...["Labware ID", "Kind", "PyLabRobot resource", "Where", "Inventory", "Note"].map((h) => el("th", { text: h })))),
        el("tbody", {}, ...rows))),
      machines.length ? el("h4", { class: "lib-h4", text: "Machines" }) : null,
      machines.length ? el("div", { class: "table-wrap" }, el("table", { class: "bench-table lib-table" },
        el("thead", {}, el("tr", {}, ...["ID", "Kind", "Position", "Limits", "Note"].map((h) => el("th", { text: h })))),
        el("tbody", {}, ...machines))) : null,
      carriers ? el("p", { class: "muted lib-carriers", text: `Carriers: ${carriers}` }) : null));
}

function renderLabware() {
  const { inventory, decks } = lib.data;
  const index = inventoryIndex(inventory);
  const missing = new Set();
  for (const d of decks) for (const [id, spec] of Object.entries(d.labware)) if (spec.kind !== "trash" && !(venusType(spec) in index)) missing.add(id);
  const placed = placedTypes(decks);
  const unplaced = Object.keys(index).filter((id) => !placed.has(id));

  const summary = el("div", { class: "summary-grid lib-summary" },
    statCard("Inventory items", Object.keys(index).length,
      Object.entries(inventory).filter(([k]) => k !== "labware_library").map(([k, v]) => `${Object.keys(v).length} ${(CATEGORY_LABELS[k] || k).toLowerCase()}`).join(" · ")),
    statCard("Deck layouts", decks.length, decks.map((d) => d.file).join(" · ")),
    statCard("On a deck but not in the inventory", missing.size, [...missing].join(", ") || "none",
      missing.size ? "warn" : ""),
    statCard("In the inventory but on no deck", unplaced.length, unplaced.join(", ") || "none"));

  const meta = inventory.labware_library || {};
  const groups = Object.entries(inventory)
    .filter(([k]) => k !== "labware_library")
    .map(([category, items]) => group(CATEGORY_LABELS[category] || humanize(category), null,
      Object.values(items).map((item) => inventoryCard(category, item, decks))));

  $("labware").replaceChildren(summary,
    el("p", { class: "muted lib-sub", text: `${meta.source || "VENUS library"} · ${meta.description || ""}` }),
    ...groups,
    group("Deck layouts", "Where each labware ID used by the protocols sits on the STARlet.", decks.map((d) => deckCard(d, index))));
}

function statCard(label, value, detail, kind = "") {
  return el("div", { class: `summary-card ${kind}` },
    el("h3", { text: label }),
    el("div", { class: "big" }, el("span", { text: String(value) })),
    el("p", { class: "muted lib-stat-detail", text: detail }));
}

// ---------- knowledge tab ----------

const joined = (t) => (Array.isArray(t) ? t.join(" ") : t);
const list = (v) => (Array.isArray(v) ? v : [v]);

function conditionText(cond) {
  const parts = [];
  if (cond.error) parts.push(`PyLabRobot raises ${list(cond.error).join(" or ")}`);
  if (cond.message_contains) parts.push(`its message contains “${cond.message_contains}”`);
  if (cond.device_code) parts.push(`the device reports ${cond.device_code}`);
  if (cond.action) parts.push(`the step is ${list(cond.action).join(" or ")}`);
  if (cond.action_is_not) parts.push(`the step is not ${list(cond.action_is_not).join(" or ")}`);
  if (cond.reagent_loaded === true) parts.push("the scientist loads this labware before the run");
  if (cond.reagent_loaded === false) parts.push("the scientist does not load this labware (earlier steps fill it)");
  return parts.join(", and ");
}

function whenView(entry) {
  if (!("when" in entry)) return el("p", { class: "muted", text: "Any error no entry above matches (catch-all)." });
  const conds = list(entry.when);
  if (conds.length === 1) return el("p", { text: conditionText(conds[0]) });
  return el("div", {}, el("p", { text: "Any of:" }), el("ul", { class: "fixes" }, ...conds.map((c) => el("li", { text: conditionText(c) }))));
}

function tally(obj) {
  const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return el("span", { class: "muted", text: "none" });
  return el("span", { class: "lib-chips" }, ...entries.map(([k, n]) => chip(`${k} × ${n}`)));
}

function observedView(obs) {
  if (!obs) return el("p", { class: "muted", text: "Not seen in a recorded run yet." });
  const rate = obs.repair_attempts ? `${obs.resolved} of ${obs.repair_attempts} repair attempts` : "no repair attempts";
  const dl = el("dl", { class: "kv" },
    el("dt", { text: "Failures seen" }), el("dd", { text: String(obs.seen) }),
    el("dt", { text: "Resolved" }), el("dd", { text: rate }),
    el("dt", { text: "Resolved by" }), el("dd", {}, tally(obs.resolved_by)),
    obs.escalations ? el("dt", { text: "Escalated" }) : null,
    obs.escalations ? el("dd", { text: `${obs.escalations} time(s): the model reasoned past this entry; ${obs.escalations_resolved || 0} of those resolved it` }) : null,
    el("dt", { text: "Edits rejected" }), el("dd", {}, tally(obs.rejected)),
    el("dt", { text: "Protocols" }), el("dd", { class: "mono", text: obs.protocols.join(", ") }),
    el("dt", { text: "Models" }), el("dd", { class: "mono", text: obs.models.join(", ") }),
    el("dt", { text: "Seen" }), el("dd", { text: obs.first_seen === obs.last_seen ? obs.first_seen : `${obs.first_seen} to ${obs.last_seen}` }));
  const examples = (obs.examples || []).slice().reverse().map((x) => el("tr", {},
    el("td", { text: x.date }), el("td", { class: "mono", text: x.protocol }), el("td", { text: x.step ?? "–" }),
    el("td", { class: "mono", text: x.raw_error || "" }), el("td", { text: x.outcome })));
  return el("div", {}, dl, examples.length ? el("details", {},
    el("summary", { text: `Most recent ${plural(examples.length, "failure")}` }),
    el("div", { class: "table-wrap" }, el("table", { class: "bench-table lib-table" },
      el("thead", {}, el("tr", {}, ...["Date", "Protocol", "Step", "Raw error", "Outcome"].map((h) => el("th", { text: h })))),
      el("tbody", {}, ...examples)))) : null);
}

function entryCard(entry, position) {
  const obs = entry.observed;
  const status = !obs ? chip("not seen yet")
    : chip(`seen ${obs.seen} · resolved ${obs.resolved}/${obs.repair_attempts}`, obs.resolved ? "ok" : "bad");
  const fixes = entry.fixes || [];
  const search = [entry.id, entry.code, entry.title, joined(entry.explanation), ...fixes.map(joined), joined(entry.notes || ""), JSON.stringify(entry.when || {})].join(" ");
  const node = card(search,
    el("header", {},
      el("span", { class: "muted lib-pos", text: `#${position}` }),
      el("span", { class: "badge", text: entry.code }),
      el("div", {}, el("h3", { text: entry.title }), el("div", { class: "muted mono lib-title", text: entry.id })),
      el("div", { class: "lib-chips" }, status)),
    el("div", { class: "block" }, el("h4", { text: "Applies when" }), whenView(entry),
      entry.facts?.length ? el("p", { class: "muted", text: `Uses facts: ${entry.facts.join(", ")}` }) : null),
    el("div", { class: "block" }, el("h4", { text: "Explanation sent to the model" }), el("p", {}, template(joined(entry.explanation)))),
    el("div", { class: "block" }, el("h4", { text: "Suggested fixes sent to the model" }),
      fixes.length ? el("ol", { class: "fixes" }, ...fixes.map((f) => el("li", {}, template(joined(f)))))
        : el("p", { class: "muted", text: "None: the model gets only the explanation." })),
    entry.notes ? el("div", { class: "block lib-notes" }, el("h4", { text: "Notes (for people, not sent to the model)" }), el("p", { text: joined(entry.notes) })) : null,
    el("div", { class: "block" }, el("h4", { text: "Observed in runs" }), observedView(obs)));
  node.dataset.seen = obs ? "1" : "";
  return node;
}

function renderKnowledge() {
  const kb = lib.data.knowledge;
  const entries = kb.entries;
  const seen = entries.filter((e) => e.observed);
  const total = (k) => seen.reduce((n, e) => n + (e.observed[k] || 0), 0);
  const codes = new Set(entries.map((e) => e.code));
  const unrecognized = entries.find((e) => e.code === "UNRECOGNIZED")?.observed?.seen || 0;

  const summary = el("div", { class: "summary-grid lib-summary" },
    statCard("Entries", entries.length, `${codes.size} error codes`),
    statCard("Seen in recorded runs", seen.length, seen.length ? seen.map((e) => e.code).join(", ") : "no runs recorded yet"),
    statCard("Failures recorded", total("seen"), `${total("resolved")} resolved of ${total("repair_attempts")} repair attempts`),
    statCard("Proposals waiting for review", (kb.proposals || []).filter((p) => p.status === "pending").length,
      `${(kb.proposals || []).filter((p) => p.status === "approved").length} approved · ${(kb.proposals || []).filter((p) => p.status === "rejected").length} rejected`,
      (kb.proposals || []).some((p) => p.status === "pending") ? "warn" : ""),
    statCard("Unrecognized errors", unrecognized, unrecognized ? "Add an entry for them: see the last card" : "every recorded failure had an entry", unrecognized ? "warn" : ""));

  const glossary = el("section", { class: "card lib-card" },
    el("header", {}, el("h3", { text: "How to read an entry" })),
    el("div", { class: "block" }, ...kb.about.map((t) => el("p", { text: t }))),
    el("div", { class: "block" }, el("h4", { text: "Fields" }), specView(kb.fields)),
    el("div", { class: "block" }, el("h4", { text: "Placeholders and facts" }),
      el("p", { class: "muted", text: "Highlighted words in an explanation or fix are filled in from the failing step and the deck when the error happens." }),
      specView({ ...kb.placeholders, ...Object.fromEntries(Object.entries(kb.facts).map(([k, v]) => [`fact: ${k}`, v])) })));
  glossary.dataset.search = "";
  glossary.dataset.always = "1";

  const props = kb.proposals || [];
  const pending = props.filter((p) => p.status === "pending");
  const reviewed = props.filter((p) => p.status !== "pending").reverse();
  const proposalCard = (p) => {
    const c = card(`${p.id} ${p.kind} ${p.target} ${p.proposed.fix} ${p.proposed.why} ${p.proposed.code || ""}`,
      el("div", { class: "block" }, proposalView(p, () => setTimeout(reload, 600))));
    c.dataset.seen = "1";
    return c;
  };

  $("knowledge").replaceChildren(...[summary,
    pending.length ? group(`Waiting for your review (${pending.length})`,
      "Proposed by the model after a failure kept coming back. Each one's fix healed a protocol; approving adds it to the entries the model sees in future runs.",
      pending.map(proposalCard)) : null,
    group("Entries, in matching order", "The first entry whose conditions match a failure explains it.", entries.map((e, i) => entryCard(e, i + 1))),
    reviewed.length ? group("Reviewed proposals", "Kept as a record of what was approved and turned down.", reviewed.map(proposalCard)) : null,
    el("section", { class: "bench-section" }, el("h2", { text: "Reference" }), glossary)].filter(Boolean));
}

// ---------- tabs and filter ----------

function setTab(tab) {
  lib.tab = tab;
  for (const name of ["labware", "knowledge"]) {
    $(name).hidden = name !== tab;
    $(`side-${name}`).hidden = name !== tab;
    $(`tab-${name}`).setAttribute("aria-selected", String(name === tab));
  }
  $("seen-only-field").hidden = tab !== "knowledge";
  if (location.hash !== `#${tab}`) history.replaceState(null, "", `#${tab}`);
  applyFilter();
}

function applyFilter() {
  const q = $("filter").value.trim().toLowerCase();
  const seenOnly = lib.tab === "knowledge" && $("seen-only").checked;
  const root = $(lib.tab);
  let shown = 0, all = 0;
  for (const c of root.querySelectorAll(".lib-card")) {
    if (c.dataset.always) continue;
    all += 1;
    const visible = (!q || c.dataset.search.includes(q)) && (!seenOnly || c.dataset.seen);
    c.hidden = !visible;
    if (visible) shown += 1;
  }
  for (const g of root.querySelectorAll(".lib-group")) g.hidden = ![...g.querySelectorAll(".lib-card")].some((c) => !c.hidden);
  $("lib-text").textContent = q || seenOnly ? `${shown} of ${all} shown` : `${all} ${lib.tab === "labware" ? "items and decks" : "entries"}`;
}

async function reload() {
  lib.data = await (await fetch("/api/library")).json();
  renderLabware();
  renderKnowledge();
  setTab(lib.tab);
}

async function init() {
  try {
    lib.data = await (await fetch("/api/library")).json();
  } catch (err) {
    $("lib-chip").className = "chip bad";
    $("lib-chip").textContent = "Error";
    $("lib-text").textContent = `Could not load the library: ${err.message}`;
    return;
  }
  $("lib-chip").className = "chip ok";
  $("lib-chip").textContent = "Loaded";
  renderLabware();
  renderKnowledge();
  for (const b of document.querySelectorAll("[data-tab]")) b.addEventListener("click", () => setTab(b.dataset.tab));
  $("filter").addEventListener("input", applyFilter);
  $("seen-only").addEventListener("change", applyFilter);
  const fromHash = () => setTab(location.hash === "#knowledge" ? "knowledge" : "labware");
  window.addEventListener("hashchange", fromHash);
  fromHash();
}

init();
