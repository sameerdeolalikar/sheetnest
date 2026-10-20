"use strict";
const $ = (id) => document.getElementById(id),
  clone = (v) => structuredClone(v),
  ns = "http://www.w3.org/2000/svg";
const sample = {
  version: 1,
  title: "Workshop organizer",
  stock: { width: 1200, height: 800, count: 2 },
  kerf: 4,
  parts: [
    {
      id: "shelf",
      name: "Shelf panel",
      width: 520,
      height: 280,
      quantity: 3,
      rotate: true,
    },
    {
      id: "side",
      name: "Side panel",
      width: 380,
      height: 220,
      quantity: 4,
      rotate: true,
    },
    {
      id: "divider",
      name: "Divider",
      width: 240,
      height: 160,
      quantity: 4,
      rotate: false,
    },
  ],
};
let doc = clone(sample),
  layout = null,
  id = null,
  revision = 0,
  sheet = 0,
  selected = null,
  undo = [],
  redo = [],
  busy = false,
  dirty = true;
function message(text) {
  $("status").textContent = text;
  $("status").hidden = !text;
}
function error(e) {
  $("error").textContent = e.message;
  $("error").hidden = false;
}
function controls() {
  document
    .querySelectorAll("button,input,select")
    .forEach((el) => (el.disabled = busy));
  $("undo").disabled = busy || !undo.length;
  $("redo").disabled = busy || !redo.length;
  for (const name of ["save", "export-json", "export-svg"])
    $(name).disabled = busy || !layout;
  $("rotate-piece").disabled =
    busy ||
    !selected ||
    !doc.parts.find((p) => selected.startsWith(p.id + ":"))?.rotate;
}
async function api(route, data) {
  const response = await fetch(
    "/api/" + route,
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "SheetNest",
          },
          body: JSON.stringify(data),
        },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Operation failed.");
  return result;
}
async function task(text, operation) {
  if (busy) return;
  busy = true;
  controls();
  $("error").hidden = true;
  message(text);
  try {
    await operation();
  } catch (e) {
    error(e);
    message("");
  } finally {
    busy = false;
    controls();
  }
}
function changed() {
  dirty = true;
  layout = null;
  undo = [];
  redo = [];
  selected = null;
  $("revision").textContent = "Unsaved changes · generate a new layout";
  renderLayout();
  controls();
}
function field(value, type, label, change) {
  const el = document.createElement("input");
  el.type = type;
  el.setAttribute("aria-label", label);
  if (type === "checkbox") el.checked = value;
  else el.value = value;
  el.addEventListener("change", () => {
    change(
      type === "checkbox"
        ? el.checked
        : type === "number"
          ? Number(el.value)
          : el.value,
    );
    changed();
  });
  return el;
}
function renderForm() {
  for (const [name, value] of Object.entries({
    title: doc.title,
    "stock-width": doc.stock.width,
    "stock-height": doc.stock.height,
    "stock-count": doc.stock.count,
    kerf: doc.kerf,
  }))
    $(name).value = value;
  $("parts").replaceChildren();
  doc.parts.forEach((part, index) => {
    const row = document.createElement("tr");
    for (const [key, type] of [
      ["name", "text"],
      ["width", "number"],
      ["height", "number"],
      ["quantity", "number"],
      ["rotate", "checkbox"],
    ]) {
      const cell = document.createElement("td");
      cell.append(
        field(
          part[key],
          type,
          `${key} for part ${index + 1}`,
          (v) => (part[key] = v),
        ),
      );
      row.append(cell);
    }
    const cell = document.createElement("td"),
      remove = document.createElement("button");
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${part.name}`);
    remove.addEventListener("click", () => {
      doc.parts.splice(index, 1);
      changed();
      renderForm();
    });
    cell.append(remove);
    row.append(cell);
    $("parts").append(row);
  });
  controls();
}
function svgElement(name, attrs = {}, text) {
  const e = document.createElementNS(ns, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}
function renderLayout() {
  $("placed").textContent = layout?.placements.length ?? 0;
  $("sheets").textContent = layout?.sheets_used ?? 0;
  $("utilization").textContent = (layout?.utilization ?? 0) + "%";
  $("unplaced-count").textContent = layout?.unplaced.length ?? 0;
  $("sheet-tabs").replaceChildren();
  $("drawing").replaceChildren();
  $("piece-editor").hidden = true;
  $("unplaced").textContent = "";
  if (!layout) {
    $("drawing").textContent = "Generate a layout after editing your cut list.";
    return;
  }
  sheet = Math.min(sheet, doc.stock.count - 1);
  for (let i = 0; i < doc.stock.count; i++) {
    const button = document.createElement("button");
    button.textContent = `Sheet ${i + 1}`;
    button.className = i === sheet ? "selected" : "";
    button.setAttribute("aria-pressed", String(i === sheet));
    button.addEventListener("click", () => {
      sheet = i;
      selected = null;
      renderLayout();
      controls();
    });
    $("sheet-tabs").append(button);
  }
  const svg = svgElement("svg", {
    viewBox: `-20 -20 ${doc.stock.width + 40} ${doc.stock.height + 40}`,
    role: "group",
    "aria-label": `Sheet ${sheet + 1}, ${doc.stock.width} by ${doc.stock.height} millimetres`,
  });
  svg.append(
    svgElement("rect", {
      x: 0,
      y: 0,
      width: doc.stock.width,
      height: doc.stock.height,
      fill: "#ffffff",
      stroke: "#536b78",
      "stroke-width": 2,
    }),
  );
  const palette = ["#b9dcd8", "#d6c9ed", "#f2d4ad", "#c3d8ef", "#efc9ce"];
  for (const piece of layout.placements.filter((p) => p.sheet === sheet)) {
    const group = svgElement("g", {
      role: "button",
      tabindex: 0,
      "aria-label": `${piece.name} ${piece.id}, x ${piece.x}, y ${piece.y}`,
    });
    const color =
      palette[
        doc.parts.findIndex((p) => piece.id.startsWith(p.id + ":")) %
          palette.length
      ];
    group.append(
      svgElement("rect", {
        x: piece.x,
        y: piece.y,
        width: piece.width,
        height: piece.height,
        fill: color,
        stroke: selected === piece.id ? "#1b6572" : "#607b83",
        "stroke-width": selected === piece.id ? 6 : 2,
        class: "piece",
      }),
    );
    const size = Math.min(22, piece.width / 8, piece.height / 4);
    group.append(
      svgElement(
        "text",
        {
          x: piece.x + piece.width / 2,
          y: piece.y + piece.height / 2,
          "text-anchor": "middle",
          "font-size": size,
          fill: "#24313e",
        },
        piece.name,
      ),
    );
    group.append(
      svgElement(
        "text",
        {
          x: piece.x + piece.width / 2,
          y: piece.y + piece.height / 2 + size * 1.4,
          "text-anchor": "middle",
          "font-size": size * 0.75,
          fill: "#24313e",
        },
        `${piece.width} × ${piece.height}`,
      ),
    );
    const choose = () => {
      selected = piece.id;
      renderLayout();
      controls();
    };
    group.addEventListener("click", choose);
    group.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose();
        $("x").focus();
      }
    });
    svg.append(group);
  }
  $("drawing").append(svg);
  $("unplaced").textContent = layout.unplaced.length
    ? `Not placed: ${layout.unplaced.join(", ")}. Add sheets, reduce dimensions, or try another cut list.`
    : `All requested pieces placed. Unused area: ${(layout.unused_area / 1e6).toFixed(3)} m², including cut spacing.`;
  const piece = layout.placements.find((p) => p.id === selected);
  if (piece) {
    $("piece-editor").hidden = false;
    $("piece-name").textContent = `Adjust ${piece.name} · ${piece.id}`;
    $("x").value = piece.x;
    $("y").value = piece.y;
    $("piece-sheet").replaceChildren();
    for (let i = 0; i < doc.stock.count; i++)
      $("piece-sheet").add(new Option(`Sheet ${i + 1}`, i));
    $("piece-sheet").value = piece.sheet;
  }
}
async function library() {
  const records = await api("projects");
  $("library").replaceChildren();
  $("library").add(new Option("Select a saved project", ""));
  records.forEach((r) =>
    $("library").add(new Option(`${r.title} · v${r.revision}`, r.id)),
  );
  if (id) $("library").value = id;
}
async function generate() {
  const result = await api("plan", doc);
  doc = result.document;
  layout = result.layout;
  undo = [];
  redo = [];
  selected = null;
  renderForm();
  renderLayout();
  message(
    "Layout generated. Select any piece to inspect or adjust its position.",
  );
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type })),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function move(rotate) {
  if (!layout || !selected) return;
  const next = clone(layout),
    p = next.placements.find((p) => p.id === selected);
  p.x = Number($("x").value);
  p.y = Number($("y").value);
  p.sheet = Number($("piece-sheet").value);
  if (rotate) p.rotated = !p.rotated;
  const checked = await api("validate", { document: doc, layout: next });
  undo.push(clone(layout));
  undo = undo.slice(-40);
  redo = [];
  layout = checked;
  dirty = true;
  sheet = p.sheet;
  $("revision").textContent = "Unsaved layout changes";
  renderLayout();
  message("Position validated: within the sheet, with required spacing.");
}
$("plan").addEventListener("click", () =>
  task("Planning the cut list…", generate),
);
for (const name of [
  "title",
  "stock-width",
  "stock-height",
  "stock-count",
  "kerf",
])
  $(name).addEventListener("change", () => {
    if (name === "title") doc.title = $(name).value;
    else if (name === "kerf") doc.kerf = Number($(name).value);
    else doc.stock[name.slice(6)] = Number($(name).value);
    changed();
  });
$("add-part").addEventListener("click", () => {
  doc.parts.push({
    id: "part-" + Date.now(),
    name: "New part",
    width: 100,
    height: 100,
    quantity: 1,
    rotate: true,
  });
  changed();
  renderForm();
});
$("move").addEventListener("click", () =>
  task("Checking the adjusted layout…", () => move(false)),
);
$("rotate-piece").addEventListener("click", () =>
  task("Checking rotation and spacing…", () => move(true)),
);
$("undo").addEventListener("click", () => {
  if (!undo.length) return;
  redo.push(clone(layout));
  layout = undo.pop();
  dirty = true;
  renderLayout();
  controls();
});
$("redo").addEventListener("click", () => {
  if (!redo.length) return;
  undo.push(clone(layout));
  layout = redo.pop();
  dirty = true;
  renderLayout();
  controls();
});
$("save").addEventListener("click", () =>
  task("Saving to the local library…", async () => {
    const saved = await api("save", { id, revision, document: doc, layout });
    id = saved.id;
    revision = saved.revision;
    dirty = false;
    $("revision").textContent = `Saved revision ${revision}`;
    await library();
    message("Project and validated layout saved locally.");
  }),
);
$("open").addEventListener("click", () => {
  const key = $("library").value;
  if (!key) return;
  if (dirty && !confirm("Discard unsaved changes and open this project?"))
    return;
  task("Opening saved project…", async () => {
    const saved = await api("projects/" + key);
    doc = saved.document;
    layout = saved.layout;
    id = saved.id;
    revision = saved.revision;
    dirty = false;
    undo = [];
    redo = [];
    selected = null;
    sheet = 0;
    renderForm();
    renderLayout();
    $("revision").textContent = `Saved revision ${revision}`;
    message("Project restored from the local library.");
  });
});
$("sample").addEventListener("click", () => {
  if (dirty && !confirm("Replace the current unsaved project with the sample?"))
    return;
  task("Preparing sample project…", async () => {
    doc = clone(sample);
    id = null;
    revision = 0;
    dirty = true;
    sheet = 0;
    $("revision").textContent = "Unsaved sample";
    await generate();
  });
});
$("export-json").addEventListener("click", () =>
  task("Validating project export…", async () => {
    const checked = await api("validate", { document: doc, layout });
    download(
      "sheetnest-project.json",
      JSON.stringify({ document: doc, layout: checked }, null, 2) + "\n",
      "application/json",
    );
    message("Validated project downloaded.");
  }),
);
$("export-svg").addEventListener("click", () =>
  task("Validating sheet export…", async () => {
    await api("validate", { document: doc, layout });
    const svg = $("drawing").querySelector("svg").cloneNode(true);
    svg.setAttribute("xmlns", ns);
    svg.setAttribute("width", doc.stock.width + "mm");
    svg.setAttribute("height", doc.stock.height + "mm");
    svg.setAttribute("viewBox", `0 0 ${doc.stock.width} ${doc.stock.height}`);
    download(
      `sheetnest-sheet-${sheet + 1}.svg`,
      new XMLSerializer().serializeToString(svg),
      "image/svg+xml",
    );
    message(
      "SVG exported at its declared dimensions; verify print scaling independently.",
    );
  }),
);
$("print").addEventListener("click", () => window.print());
$("import").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (dirty && !confirm("Replace unsaved work with this imported project?"))
    return;
  task("Validating imported project…", async () => {
    if (file.size > 256000)
      throw new Error("Project files must be smaller than 256 KB.");
    const raw = JSON.parse(await file.text());
    const checked = await api("validate", raw);
    const normalized = await api("plan", raw.document);
    doc = normalized.document;
    layout = checked;
    id = null;
    revision = 0;
    dirty = true;
    selected = null;
    undo = [];
    redo = [];
    sheet = 0;
    renderForm();
    renderLayout();
    $("revision").textContent = "Imported · not saved";
    message("Imported project validated. Save to add it to your library.");
  });
});
renderForm();
task("Preparing your workspace…", async () => {
  await generate();
  await library();
});
