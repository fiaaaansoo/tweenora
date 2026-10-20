import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  ALLOWED_STATUSES,
  BUILT_DTS,
  DOMAINS,
  INVENTORY_PATH,
  REPORT_PATH,
  assignSubtask,
  buildInventory,
  extractApi,
  hasTypeScript,
  main,
  mergeRows,
  renderReport,
  validateRows,
} from "./api-inventory.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const needsTypeScript = { skip: !hasTypeScript() && "typescript is not installed: run npm ci in web/rive-wasm/js" };
const needsBuild = { skip: (!hasTypeScript() || !existsSync(BUILT_DTS)) && "the package is not built" };

const SYNTHETIC = `
export declare class B { base(): void; }
export declare class A extends B {
    constructor(x: number);
    static make(): A;
    private hidden;
    protected prot(): void;
    foo(a: string): void;
    foo(a: number): void;
    get v(): number;
    set v(x: number);
    opt?: string;
    readonly ro: number;
    static sv: string;
}
declare class Hidden { x: number; }
export declare const K: { readonly a: 1; readonly b: 2; };
export interface I { m(): void; p: string; }
export declare enum E { X = 1, Y = 2 }
export declare function f(): void;
export declare const c: number;
export type T = string | number;
export default A;
`;

const scratch = [];
function scratchDir() {
  const dir = mkdtempSync(path.join(tmpdir(), "api-inventory-"));
  scratch.push(dir);
  return dir;
}
after(() => {
  for (const dir of scratch) rmSync(dir, { recursive: true, force: true });
});

function extractSynthetic() {
  const file = path.join(scratchDir(), "synthetic.d.ts");
  writeFileSync(file, SYNTHETIC);
  return extractApi(file);
}

function loadInventory() {
  return JSON.parse(readFileSync(INVENTORY_PATH, "utf8"));
}

const sample = (container, name, kind = "method") => ({ id: container ? `${container}#${name}` : name, container, name, kind });

test("extraction lists declarations and public members, once each", needsTypeScript, () => {
  const ids = extractSynthetic().map((r) => r.id).sort();
  assert.deepEqual(ids, [
    "A",
    "A#constructor",
    "A#foo",
    "A#opt",
    "A#ro",
    "A#v",
    "A::make",
    "A::sv",
    "B",
    "B#base",
    "E",
    "E.X",
    "E.Y",
    "Hidden",
    "Hidden#x",
    "I",
    "I#m",
    "I#p",
    "K",
    "K.a",
    "K.b",
    "T",
    "c",
    "f",
  ]);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(!ids.includes("default"));
});

test("extraction keeps overloads in one row and skips private and protected members", needsTypeScript, () => {
  const rows = extractSynthetic();
  assert.equal(rows.find((r) => r.id === "A#foo").signatures.length, 2);
  assert.equal(rows.find((r) => r.id === "A#v").signatures.length, 2);
  assert.ok(!rows.some((r) => r.name === "hidden" || r.name === "prot"));
});

test("extraction records kinds, containers, static members and whether a declaration is exported", needsTypeScript, () => {
  const rows = new Map(extractSynthetic().map((r) => [r.id, r]));
  assert.equal(rows.get("A").kind, "class");
  assert.equal(rows.get("I").kind, "interface");
  assert.equal(rows.get("E").kind, "enum");
  assert.equal(rows.get("E.X").kind, "enumMember");
  assert.equal(rows.get("f").kind, "function");
  assert.equal(rows.get("c").kind, "variable");
  assert.equal(rows.get("T").kind, "type");
  assert.equal(rows.get("K.a").kind, "property");
  assert.equal(rows.get("A::make").static, true);
  assert.equal(rows.get("A#foo").static, false);
  assert.equal(rows.get("A#foo").container, "A");
  assert.equal(rows.get("A").container, null);
  assert.equal(rows.get("A").exported, true);
  assert.equal(rows.get("Hidden").exported, false);
  assert.equal(rows.get("Hidden#x").exported, false);
});

test("extraction follows the named imports of the entry file", needsTypeScript, () => {
  const dir = scratchDir();
  writeFileSync(path.join(dir, "wrapper.d.ts"), "export declare class W { m(): void; }\nexport declare class Unused { z(): void; }\n");
  writeFileSync(path.join(dir, "entry.d.ts"), 'import { W } from "./wrapper";\nexport declare function make(): W;\n');
  const rows = new Map(extractApi(path.join(dir, "entry.d.ts")).map((r) => [r.id, r]));
  assert.equal(rows.get("W").exported, false);
  assert.equal(rows.get("W").origin, "wrapper.d.ts");
  assert.ok(rows.has("W#m"));
  assert.ok(!rows.has("Unused"));
});

test("extraction fails loudly on an unresolved re-export", needsTypeScript, () => {
  const dir = scratchDir();
  writeFileSync(path.join(dir, "entry.d.ts"), 'export { Missing } from "./nowhere";\n');
  assert.throws(() => extractApi(path.join(dir, "entry.d.ts")));
});

test("merge keeps every hand-written column, adds new rows and reports removed and lost ones", () => {
  const fresh = [
    { id: "A", kind: "class", name: "A", container: null, static: false, signatures: ["class A"] },
    { id: "A#new", kind: "method", name: "new", container: "A", static: false, signatures: ["new(): void"] },
  ];
  const previous = [
    { id: "A", equivalent: "A (renamed)", example: "web/examples/a.html", status: "not demonstrated", reason: "no audio device", subtask: "c" },
    { id: "gone", equivalent: "gone", example: "", status: "todo", reason: "", subtask: "b" },
    { id: "gone2", equivalent: "gone2", example: "web/examples/x.html", status: "demonstrated", reason: "", subtask: "b" },
  ];
  const { rows, removed, lost } = mergeRows(fresh, previous);
  const a = rows.find((r) => r.id === "A");
  assert.deepEqual([a.equivalent, a.example, a.status, a.reason, a.subtask], ["A (renamed)", "web/examples/a.html", "not demonstrated", "no audio device", "c"]);
  const added = rows.find((r) => r.id === "A#new");
  assert.deepEqual([added.status, added.equivalent, added.example, added.reason], ["todo", "A#new", "", ""]);
  assert.deepEqual(removed, ["gone", "gone2"]);
  assert.deepEqual(lost, ["gone2"]);
});

test("validation rejects unknown statuses and sub-tasks and missing reasons or examples", () => {
  const ok = { id: "a", status: "todo", subtask: "b", reason: "", example: "" };
  assert.deepEqual(validateRows([ok]), []);
  assert.equal(validateRows([{ ...ok, status: "bogus" }]).length, 1);
  assert.equal(validateRows([{ ...ok, subtask: "z" }]).length, 1);
  assert.equal(validateRows([{ ...ok, status: "not demonstrated" }]).length, 1);
  assert.equal(validateRows([{ ...ok, status: "demonstrated" }]).length, 1);
  assert.deepEqual(validateRows([{ ...ok, status: "not demonstrated", reason: "why" }]), []);
});

function runMain(previousRows, extraArgs = []) {
  const dir = scratchDir();
  writeFileSync(path.join(dir, "api.d.ts"), "export declare class A { m(): void; }\n");
  const inventoryPath = path.join(dir, "inventory.json");
  const reportPath = path.join(dir, "report.md");
  if (previousRows) writeFileSync(inventoryPath, JSON.stringify({ rows: previousRows }));
  const code = main(["--dts", path.join(dir, "api.d.ts"), ...extraArgs], { inventoryPath, reportPath });
  return { code, inventoryPath, reportPath };
}

const handRow = (id, extra) => ({ id, equivalent: id, example: "", status: "todo", reason: "", subtask: "b", ...extra });

test("the generator writes the inventory and the report, then --check agrees", needsTypeScript, () => {
  const first = runMain(null);
  assert.equal(first.code, 0);
  const written = JSON.parse(readFileSync(first.inventoryPath, "utf8"));
  assert.deepEqual(written.rows.map((r) => r.id), ["A", "A#m"]);
  assert.equal(main(["--check", "--dts", path.join(path.dirname(first.inventoryPath), "api.d.ts")], first), 0);
  writeFileSync(first.reportPath, "stale\n");
  assert.equal(main(["--check", "--dts", path.join(path.dirname(first.inventoryPath), "api.d.ts")], first), 1);
  rmSync(first.reportPath);
  assert.equal(main(["--check", "--dts", path.join(path.dirname(first.inventoryPath), "api.d.ts")], first), 1);
});

test("the generator refuses invalid hand-written data", needsTypeScript, () => {
  assert.equal(runMain([handRow("A", { status: "bogus" })]).code, 1);
  assert.equal(runMain([handRow("A", { status: "not demonstrated" })]).code, 1);
});

test("the generator refuses to lose a row with hand-written data unless told to", needsTypeScript, () => {
  const previous = [handRow("A"), handRow("gone", { status: "demonstrated", example: "web/examples/x.html" })];
  assert.equal(runMain(previous).code, 1);
  assert.equal(runMain(previous, ["--allow-removed"]).code, 0);
  assert.equal(runMain([handRow("A"), handRow("gone")]).code, 0);
});

test("the generator reports a missing d.ts file", () => {
  assert.equal(main(["--dts", path.join(scratchDir(), "missing.d.ts")], {}), 1);
});

test("the allowed statuses are the three of the task", () => {
  assert.deepEqual(ALLOWED_STATUSES, ["todo", "demonstrated", "not demonstrated"]);
  assert.deepEqual(Object.keys(DOMAINS), ["b", "c", "d", "e", "f", "g"]);
});

test("rows are assigned to the sub-task that covers their domain", () => {
  const expected = {
    d: [sample(null, "DataType", "enum"), sample("DataType", "none", "enumMember"), sample("DataType", "trigger", "enumMember"), sample("Rive", "bind"), sample("Rive", "enums"), sample("RiveFile", "getBindableArtboard"), sample(null, "BindableArtboard", "class"), sample("ViewModelInstanceString", "value", "accessor"), sample("RiveParameters", "autoBind", "property")],
    c: [sample("Rive", "play"), sample("Rive", "setBooleanStateAtPath"), sample("Rive", "fireStateAtPath"), sample("RiveParameters", "onStateChange", "property"), sample("EventType", "StateChange", "enumMember"), sample("Event", "type", "property"), sample("EventListener", "callback", "property"), sample("LoopEvent", "type", "property"), sample("LoopType", "OneShot", "enumMember"), sample("RiveEventType", "General", "enumMember"), sample("StateMachineInputType", "Number", "enumMember"), sample("StateMachineInput", "fire"), sample("Task", "action", "property"), sample(null, "EventManager", "class")],
    e: [sample("Rive", "setTextRunValue"), sample("Rive", "resetArtboardSize"), sample("Rive", "resizeDrawingSurfaceToCanvas"), sample("Layout", "layoutScaleFactor", "property"), sample("LayoutParameters", "layoutScaleFactor", "property"), sample(null, "RiveFont", "class"), sample(null, "FontWrapper", "class"), sample(null, "decodeFont", "function")],
    f: [sample("Rive", "volume", "accessor"), sample(null, "AudioWrapper", "class"), sample("AudioWrapper", "unref"), sample(null, "decodeAudio", "function")],
    b: [sample(null, "Layout", "class"), sample("Layout", "fit", "property"), sample(null, "Fit", "enum"), sample("Rive", "startRendering"), sample("Rive", "stopRendering"), sample(null, "ImageWrapper", "class"), sample(null, "SemanticMode", "variable"), sample("Whatever", "x", "property")],
  };
  for (const [subtask, rows] of Object.entries(expected)) {
    for (const row of rows) assert.equal(assignSubtask(row), subtask, row.id);
  }
});

test("the committed inventory is consistent", () => {
  assert.ok(existsSync(INVENTORY_PATH), "run node web/parity/api-inventory.mjs");
  const inventory = loadInventory();
  const ids = inventory.rows.map((r) => r.id);
  assert.equal(new Set(ids).size, ids.length, "duplicate ids");
  assert.deepEqual(validateRows(inventory.rows), []);
  for (const row of inventory.rows) {
    assert.ok(row.equivalent, `${row.id}: no equivalent`);
    if (row.status === "demonstrated") {
      const target = path.join(repoRoot, row.example.split("#")[0]);
      assert.ok(existsSync(target), `${row.id}: ${row.example} does not exist`);
    }
  }
});

test("no row is left to do: each is demonstrated or not demonstrated with a reason", () => {
  const todo = loadInventory().rows.filter((r) => r.status === "todo").map((r) => r.id);
  assert.deepEqual(todo, []);
});

test("every demonstrated row has an example that uses the member", () => {
  const inventory = loadInventory();
  const byId = new Map(inventory.rows.map((r) => [r.id, r]));
  const sources = new Map();
  for (const row of inventory.rows) {
    if (row.status !== "demonstrated") continue;
    const file = row.example.split("#")[0];
    if (!sources.has(file)) sources.set(file, readFileSync(path.join(repoRoot, file), "utf8"));
    if (row.kind === "type" || row.kind === "interface") continue;
    const reachedThroughMembers =
      row.kind === "class" &&
      inventory.rows.some((r) => r.container === row.id && r.status === "demonstrated" && r.example === row.example);
    if (reachedThroughMembers) continue;
    const container = row.container === null ? null : byId.get(row.container);
    const selectable = container && container.kind === "enum";
    const name = selectable || row.name === "constructor" ? row.container ?? row.name : row.name;
    const mentions = new RegExp(`(^|[^\\w$])${name}([^\\w$]|$)`);
    assert.match(sources.get(file), mentions, `${row.id}: ${file} never mentions ${name}`);
  }
});

test("the inventory counts match the rows", () => {
  const inventory = loadInventory();
  const classes = inventory.rows.filter((r) => r.kind === "class" && r.container === null);
  assert.equal(inventory.counts.rows, inventory.rows.length);
  assert.equal(inventory.counts.classes, classes.length);
  assert.equal(inventory.counts.classesDeclaredInEntry, classes.filter((r) => r.origin === "rive.d.ts").length);
  assert.ok(inventory.counts.classesDeclaredInEntry >= 18, "rive.d.ts declares at least 18 classes");
  for (const subtask of Object.keys(DOMAINS)) {
    assert.equal(inventory.counts.bySubtask[subtask], inventory.rows.filter((r) => r.subtask === subtask).length, subtask);
  }
  for (const status of ALLOWED_STATUSES) {
    assert.equal(inventory.counts.byStatus[status], inventory.rows.filter((r) => r.status === status).length, status);
  }
});

test("the report lists every row, shows reasons and is up to date", () => {
  const inventory = loadInventory();
  const report = renderReport(inventory);
  assert.equal(readFileSync(REPORT_PATH, "utf8").replace(/\r\n/g, "\n"), report);
  for (const row of inventory.rows) {
    assert.ok(report.includes(`\`${row.id}\``), `${row.id} missing from the report`);
  }
});

test("the report shows the status, the reason and the example of hand-written rows", () => {
  const inventory = {
    ...loadInventory(),
    rows: [
      { id: "X#a", kind: "method", name: "a", container: "X", static: false, exported: true, equivalent: "X#a", example: "web/examples/x.html", status: "demonstrated", reason: "", subtask: "b" },
      { id: "X#b", kind: "method", name: "b", container: "X", static: true, exported: false, equivalent: "X#b", example: "", status: "not demonstrated", reason: "needs a sound card", subtask: "f" },
    ],
  };
  const report = renderReport(inventory);
  assert.ok(report.includes("web/examples/x.html"));
  assert.ok(report.includes("not demonstrated: needs a sound card"));
  assert.ok(report.includes("method static (not exported)"));
});

test("when the package is built, the generator reproduces the committed inventory", needsBuild, () => {
  const committed = loadInventory();
  const { inventory, lost } = buildInventory(BUILT_DTS, committed);
  assert.deepEqual(lost, []);
  assert.deepEqual(inventory, committed);
  assert.equal(main(["--check"]), 0);
});

test("when the package is built, the inventory covers every export of rive.d.ts", needsBuild, () => {
  const inventory = loadInventory();
  const source = readFileSync(BUILT_DTS, "utf8");
  const declared = new Set();
  for (const match of source.matchAll(/^export (?:declare )?(?:abstract )?(?:class|function|enum|const|interface|type) (\w+)/gm)) {
    declared.add(match[1]);
  }
  for (const match of source.matchAll(/^export \{ ([^}]+) \};/gm)) {
    for (const part of match[1].split(",")) {
      const name = part.replace(/\btype\b/, "").trim().split(/\s+as\s+/).pop();
      if (name) declared.add(name);
    }
  }
  const listed = new Set(inventory.rows.filter((r) => r.container === null).map((r) => r.name));
  for (const name of declared) {
    assert.ok(listed.has(name), `${name} exported by rive.d.ts but not in the inventory`);
  }
});

test("when the package is built, an independent pass finds the same members in every class", needsBuild, () => {
  const inventory = loadInventory();
  const source = readFileSync(BUILT_DTS, "utf8").replace(/\r\n/g, "\n");
  let classesChecked = 0;
  for (const match of source.matchAll(/^(?:export )?declare class (\w+)[^\n{]*\{\n([\s\S]*?)^\}/gm)) {
    const [, name, body] = match;
    const found = new Set();
    for (const line of body.split("\n")) {
      if (!line.startsWith("    ") || line.startsWith("     ")) continue;
      const text = line.trim();
      if (/^(private|protected|\/\*\*|\*|\/\/|\})/.test(text)) continue;
      const parsed = text.match(/^((?:static|readonly|abstract)\s+)*(?:(?:get|set)\s+)?([A-Za-z_$][\w$]*)\??\s*[(:<;=]/);
      if (parsed) found.add(`${(parsed[1] ?? "").includes("static")}:${parsed[2]}`);
    }
    const listed = new Set(inventory.rows.filter((r) => r.container === name).map((r) => `${r.static}:${r.name}`));
    assert.deepEqual([...found].sort(), [...listed].sort(), name);
    classesChecked += 1;
  }
  assert.equal(classesChecked, inventory.counts.classesDeclaredInEntry);
});

test("when the package is built, its rive.d.ts is the one the inventory was made from", needsBuild, () => {
  const inventory = loadInventory();
  const hash = createHash("sha256").update(readFileSync(BUILT_DTS)).digest("hex");
  assert.equal(hash, inventory.source.sha256, "rive.d.ts changed: regenerate the inventory");
});
