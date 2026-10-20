import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const require = createRequire(import.meta.url);
const TYPESCRIPT_DIR = path.join(repoRoot, "web", "rive-wasm", "js", "node_modules", "typescript");

export const BUILT_DTS = path.join(repoRoot, "web", "rive-wasm", "js", "npm", "webgl2", "rive.d.ts");
export const INVENTORY_PATH = path.join(here, "api-inventory.json");
export const REPORT_PATH = path.join(repoRoot, "docs", "baseline", "api-parity-p3-3.md");
export const ALLOWED_STATUSES = ["todo", "demonstrated", "not demonstrated"];
export const DOMAINS = {
  b: "Loading and playback",
  c: "Animations and state machines",
  d: "Data binding and view models",
  e: "Text and layout",
  f: "Audio",
  g: "Scripting",
};
export const NOTES = {
  g: "No rows: the package's JavaScript API exposes no scripting-specific member. A file's Luau scripts run in the WASM module; P3-3g demonstrates that a file with scripts loads, draws and reacts, without an inventory row.",
};
export const PERIMETER = [
  "The public API is everything that the `rive.d.ts` of the `@tweenora/webgl2` package (`typings` field) declares, re-exports or makes reachable:",
  "(1) the exported classes, interfaces, enumerations, types, functions and constants;",
  "(2) the non-exported declarations of `rive.d.ts` (`BindableArtboard`, `EventManager`...) and the types imported from the neighboring modules",
  "`./utils`, `./semantics` and `./runtimeLoader` (`ImageWrapper`, `AccessibilityOverlay`...) that the public signatures",
  "return or accept; they carry the mention \"not exported\";",
  "(3) for each of them, its public members (methods, properties, accessors, constructor, static members, enumeration values;",
  "overloads of the same name form one row), and the values of object-literal constants (`DeprecationKeys`, `Testing`).",
  "Private and protected members are excluded; an inherited member is listed once, on the class that declares it.",
  "Excluded: the rest of `rive_advanced.mjs.d.ts`, the low-level API of the WASM module (`RiveCanvas`, renderers, paths) that `rive.d.ts` only exposes through",
  "types; `FileAsset`, `AudioAsset`, `FontAsset` and `ImageAsset`, re-exported by `rive.d.ts`, are however listed; the default export,",
  "which designates a class already listed; the content of the literal types of a `type` alias.",
  "Members `internal*`, `selfUnref` or `handleCallbacks` are public in the `.d.ts`: a `not demonstrated` row with the reason \"internal member\" is allowed.",
].join(" ");

const CONTAINER_OWNERS = [
  [/^(ViewModel|DataEnum|DataType$|BindableArtboard$|BaseArtboard$|Artboard$)/, "d"],
  [/^(StateMachineInput|EventType$|LoopType$|RiveEventType$|Event$|LoopEvent$|EventListener$|EventManager$|TaskQueueManager$|Task$)/, "c"],
  [/^(Layout$|Fit$|Alignment$|Testing$|DeprecationKeys$|SemanticMode$)/, "b"],
];
const NAME_RULES = [
  [/viewmodel|databind|dataenum|autobind|bindable|(^|\s)(bind|enums)$/i, "d"],
  [/script/i, "g"],
  [/audio|volume|sound|mute/i, "f"],
  [/text|font/i, "e"],
  [/layoutscalefactor|resetartboardsize|resize|drawingsurface|devicepixelratio|canvassize|responsive|artboardwidth|artboardheight|layout/i, "e"],
  [/rendering/i, "b"],
  [/statechange|statepath|atpath|play|pause|stop|reset|animation|statemachine|input|event|loop|scrub|speed|trigger|advance|timeline|listener|touch|pointer|hit/i, "c"],
];

const PRIORITY_NAMES = [[/^layoutScaleFactor$/, "e"]];

export function assignSubtask(row) {
  for (const [pattern, subtask] of PRIORITY_NAMES) {
    if (pattern.test(row.name)) return subtask;
  }
  const owner = row.container ?? row.name;
  for (const [pattern, subtask] of CONTAINER_OWNERS) {
    if (pattern.test(owner)) return subtask;
  }
  const subject = `${row.container ?? ""} ${row.name}`;
  for (const [pattern, subtask] of NAME_RULES) {
    if (pattern.test(subject)) return subtask;
  }
  return "b";
}

function loadTypeScript() {
  try {
    return require(TYPESCRIPT_DIR);
  } catch (error) {
    if (error.code === "MODULE_NOT_FOUND") {
      throw new Error(`typescript not found in ${TYPESCRIPT_DIR}: run npm ci in web/rive-wasm/js`);
    }
    throw error;
  }
}

export function hasTypeScript() {
  return existsSync(path.join(TYPESCRIPT_DIR, "package.json"));
}

export function extractApi(dtsPath) {
  const ts = loadTypeScript();
  const program = ts.createProgram([dtsPath], {
    noEmit: true,
    skipLibCheck: true,
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Node10,
    types: [],
  });
  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile(dtsPath);
  const moduleSymbol = checker.getSymbolAtLocation(sourceFile);
  const rows = [];
  const seen = new Set();
  const text = (node) => node.getText().replace(/\s+/g, " ").trim();
  const header = (node) => text(node).split("{")[0].trim();
  const flagsOf = (node) => ts.getCombinedModifierFlags(node);
  const isHidden = (member) =>
    (flagsOf(member) & (ts.ModifierFlags.Private | ts.ModifierFlags.Protected)) !== 0 ||
    (member.name && ts.isPrivateIdentifier(member.name));
  const isStatic = (member) => (flagsOf(member) & ts.ModifierFlags.Static) !== 0;
  const originOf = (declaration) => path.basename(declaration.getSourceFile().fileName);

  const memberName = (member) => {
    if (ts.isConstructorDeclaration(member)) return "constructor";
    if (ts.isIndexSignatureDeclaration(member)) return "[index]";
    if (ts.isCallSignatureDeclaration(member)) return "(call)";
    if (ts.isConstructSignatureDeclaration(member)) return "(new)";
    return member.name ? member.name.getText() : null;
  };
  const memberKind = (member) => {
    if (ts.isGetAccessorDeclaration(member) || ts.isSetAccessorDeclaration(member)) return "accessor";
    if (ts.isMethodDeclaration(member) || ts.isMethodSignature(member)) return "method";
    if (ts.isConstructorDeclaration(member) || ts.isConstructSignatureDeclaration(member)) return "constructor";
    return "property";
  };

  const addMembers = (container, origin, exported, nodes) => {
    const groups = new Map();
    for (const member of nodes) {
      if (isHidden(member)) continue;
      const name = memberName(member);
      if (name === null) continue;
      const isStaticMember = isStatic(member);
      const key = `${isStaticMember ? "::" : "#"}${name}`;
      if (!groups.has(key)) {
        groups.set(key, { id: `${container}${key}`, kind: memberKind(member), name, container, static: isStaticMember, exported, origin, signatures: [] });
      }
      groups.get(key).signatures.push(text(member));
    }
    rows.push(...groups.values());
  };

  const kindOf = (declarations) => {
    if (declarations.some(ts.isClassDeclaration)) return "class";
    if (declarations.some(ts.isInterfaceDeclaration)) return "interface";
    if (declarations.some(ts.isEnumDeclaration)) return "enum";
    if (declarations.some(ts.isFunctionDeclaration)) return "function";
    if (declarations.some(ts.isVariableDeclaration)) return "variable";
    if (declarations.some(ts.isTypeAliasDeclaration)) return "type";
    return null;
  };

  const addDeclaration = (name, symbol, exported) => {
    if (seen.has(name)) return;
    const declarations = symbol.declarations ?? [];
    const kind = kindOf(declarations);
    if (kind === null) {
      throw new Error(`${name}: declaration unresolved or of a kind not handled, check the imports of ${dtsPath}`);
    }
    seen.add(name);
    const origin = originOf(declarations[0]);
    const withBody = kind === "class" || kind === "interface" || kind === "enum";
    rows.push({
      id: name,
      kind,
      name,
      container: null,
      static: false,
      exported,
      origin,
      signatures: declarations.map((d) => (withBody ? header(d) : text(d))),
    });
    if (kind === "class" || kind === "interface") {
      for (const declaration of declarations) {
        if (ts.isClassDeclaration(declaration) || ts.isInterfaceDeclaration(declaration)) {
          addMembers(name, origin, exported, declaration.members);
        }
      }
    } else if (kind === "enum") {
      for (const declaration of declarations.filter(ts.isEnumDeclaration)) {
        for (const member of declaration.members) {
          rows.push({
            id: `${name}.${member.name.getText()}`,
            kind: "enumMember",
            name: member.name.getText(),
            container: name,
            static: false,
            exported,
            origin,
            signatures: [text(member)],
          });
        }
      }
    } else if (kind === "variable") {
      const type = checker.getTypeOfSymbolAtLocation(symbol, declarations[0]);
      if (type.flags & ts.TypeFlags.Object && type.objectFlags & ts.ObjectFlags.Anonymous) {
        for (const property of type.getProperties()) {
          rows.push({
            id: `${name}.${property.getName()}`,
            kind: "property",
            name: property.getName(),
            container: name,
            static: false,
            exported,
            origin,
            signatures: [`${property.getName()}: ${checker.typeToString(checker.getTypeOfSymbolAtLocation(property, declarations[0]))}`],
          });
        }
      }
    }
  };

  for (const exported of checker.getExportsOfModule(moduleSymbol)) {
    const exportName = exported.getName();
    if (exportName === "default") continue;
    const symbol = exported.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(exported) : exported;
    addDeclaration(exportName, symbol, true);
  }
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings)) {
      const specifier = statement.moduleSpecifier.getText().slice(1, -1);
      if (!specifier.startsWith("./") || specifier.includes("rive_advanced")) continue;
      for (const element of statement.importClause.namedBindings.elements) {
        const local = checker.getSymbolAtLocation(element.name);
        const symbol = local.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(local) : local;
        const kind = symbol.declarations ? kindOf(symbol.declarations) : null;
        if (kind === "class" || kind === "interface" || kind === "enum") addDeclaration(element.name.getText(), symbol, false);
      }
    } else if (
      (ts.isClassDeclaration(statement) || ts.isInterfaceDeclaration(statement) || ts.isEnumDeclaration(statement) || ts.isFunctionDeclaration(statement) || ts.isVariableStatement(statement)) &&
      !(flagsOf(statement) & ts.ModifierFlags.Export)
    ) {
      const names = ts.isVariableStatement(statement) ? statement.declarationList.declarations.map((d) => d.name) : [statement.name];
      for (const nameNode of names) {
        if (!nameNode) continue;
        const symbol = checker.getSymbolAtLocation(nameNode);
        if (symbol) addDeclaration(nameNode.getText(), symbol, false);
      }
    }
  }
  return rows;
}

export function validateRows(rows) {
  const errors = [];
  const owners = Object.keys(DOMAINS);
  for (const row of rows) {
    if (!ALLOWED_STATUSES.includes(row.status)) errors.push(`${row.id}: unknown status ${JSON.stringify(row.status)}`);
    if (!owners.includes(row.subtask)) errors.push(`${row.id}: unknown sub-task ${JSON.stringify(row.subtask)}`);
    if (row.status === "not demonstrated" && !String(row.reason ?? "").trim()) errors.push(`${row.id}: a not demonstrated row needs a reason`);
    if (row.status === "demonstrated" && !String(row.example ?? "").trim()) errors.push(`${row.id}: a demonstrated row needs an example`);
  }
  return errors;
}

export function isHandEdited(row) {
  return row.status !== "todo" || Boolean(row.example) || Boolean(row.reason);
}

export function mergeRows(fresh, previous) {
  const manual = new Map(previous.map((row) => [row.id, row]));
  const rows = fresh.map((row) => {
    const old = manual.get(row.id);
    return {
      ...row,
      subtask: old?.subtask ?? assignSubtask(row),
      equivalent: old?.equivalent ?? row.id,
      example: old?.example ?? "",
      status: old?.status ?? "todo",
      reason: old?.reason ?? "",
    };
  });
  const present = new Set(fresh.map((row) => row.id));
  const removed = previous.map((row) => row.id).filter((id) => !present.has(id));
  const lost = previous.filter((row) => !present.has(row.id) && isHandEdited(row)).map((row) => row.id);
  return { rows, removed, lost };
}

function countBy(rows, key, values) {
  const counts = Object.fromEntries(values.map((value) => [value, 0]));
  for (const row of rows) counts[row[key]] += 1;
  return counts;
}

export function buildInventory(dtsPath, previous) {
  const fresh = extractApi(dtsPath);
  const { rows, removed, lost } = mergeRows(fresh, previous?.rows ?? []);
  const relative = path.relative(repoRoot, dtsPath).split(path.sep).join("/");
  const classes = rows.filter((r) => r.kind === "class" && r.container === null);
  return {
    removed,
    lost,
    inventory: {
      source: { file: relative, sha256: createHash("sha256").update(readFileSync(dtsPath)).digest("hex") },
      perimeter: PERIMETER,
      counts: {
        rows: rows.length,
        classes: classes.length,
        classesDeclaredInEntry: classes.filter((r) => r.origin === "rive.d.ts").length,
        bySubtask: countBy(rows, "subtask", Object.keys(DOMAINS)),
        byStatus: countBy(rows, "status", ALLOWED_STATUSES),
      },
      rows,
    },
  };
}

const escapeCell = (value) => String(value).replace(/\|/g, "\\|");

export function renderReport(inventory) {
  const { counts, rows } = inventory;
  const lines = [
    "# JavaScript API inventory and parity (P3-3)",
    "",
    "File generated by `node web/parity/api-inventory.mjs` from `web/parity/api-inventory.json`. The Equivalent,",
    "Example and Status columns and the subtask are edited in the JSON; they are kept on every",
    "regeneration.",
    "",
    "Jest suite results, upstream defects and example limits: `jest-p3-3h.md`.",
    "",
    "Convention (D6, minimal renaming): the identifiers of the `@tweenora/webgl2` package API are those of",
    "upstream; the equivalent of a function of Rive's API is the same function in the package.",
    "",
    "## Scope",
    "",
    inventory.perimeter,
    "",
    `Source: \`${inventory.source.file}\` (sha256 \`${inventory.source.sha256}\`).`,
    "",
    "## Summary",
    "",
    `${counts.rows} rows, including ${counts.classes} classes (${counts.classesDeclaredInEntry} declared in \`rive.d.ts\`, ${counts.classes - counts.classesDeclaredInEntry} from the neighboring modules).`,
    "",
    "| Subtask | Domain | Rows | Todo | Demonstrated | Not demonstrated |",
    "|---|---|---|---|---|---|",
  ];
  for (const [subtask, label] of Object.entries(DOMAINS)) {
    const own = rows.filter((r) => r.subtask === subtask);
    const count = (status) => own.filter((r) => r.status === status).length;
    lines.push(`| P3-3${subtask} | ${label} | ${own.length} | ${count("todo")} | ${count("demonstrated")} | ${count("not demonstrated")} |`);
  }
  lines.push("", `Total: ${counts.byStatus["todo"]} todo, ${counts.byStatus["demonstrated"]} demonstrated, ${counts.byStatus["not demonstrated"]} not demonstrated.`);
  for (const [subtask, label] of Object.entries(DOMAINS)) {
    const own = rows.filter((r) => r.subtask === subtask);
    lines.push("", `## P3-3${subtask}: ${label}`, "");
    if (own.length === 0 && NOTES[subtask]) {
      lines.push(NOTES[subtask]);
      continue;
    }
    lines.push("| Function | Type | Equivalent | Example | Status |", "|---|---|---|---|---|");
    for (const row of own) {
      const status = row.status === "not demonstrated" ? `not demonstrated: ${row.reason}` : row.status;
      const type = `${row.kind}${row.static ? " static" : ""}${row.exported === false ? " (not exported)" : ""}`;
      lines.push(`| \`${escapeCell(row.id)}\` | ${type} | ${escapeCell(row.equivalent)} | ${escapeCell(row.example || "")} | ${escapeCell(status)} |`);
    }
  }
  return lines.join("\n") + "\n";
}

function readPrevious(inventoryPath) {
  return existsSync(inventoryPath) ? JSON.parse(readFileSync(inventoryPath, "utf8")) : null;
}

export function main(argv, paths = {}) {
  const inventoryPath = paths.inventoryPath ?? INVENTORY_PATH;
  const reportPath = paths.reportPath ?? REPORT_PATH;
  const check = argv.includes("--check");
  const allowRemoved = argv.includes("--allow-removed");
  const dtsIndex = argv.indexOf("--dts");
  const dtsPath = dtsIndex >= 0 ? path.resolve(argv[dtsIndex + 1]) : BUILT_DTS;
  const previous = readPrevious(inventoryPath);
  if (!existsSync(dtsPath)) {
    console.error(`error: ${dtsPath} not found: build the package first (bash web/build_webgl2_package.sh)`);
    return 1;
  }
  let built;
  try {
    built = buildInventory(dtsPath, previous);
  } catch (error) {
    console.error(`error: ${error.message}`);
    return 1;
  }
  const { inventory, removed, lost } = built;
  const errors = validateRows(inventory.rows);
  if (errors.length) {
    console.error(`error: invalid inventory data:\n  ${errors.join("\n  ")}`);
    return 1;
  }
  if (lost.length && !allowRemoved) {
    console.error(`error: rows with hand-written data are no longer in the API: ${lost.join(", ")}\n  rename them in ${inventoryPath} or pass --allow-removed`);
    return 1;
  }
  const json = JSON.stringify(inventory, null, 2) + "\n";
  const report = renderReport(inventory);
  if (check) {
    const stale =
      !previous ||
      readFileSync(inventoryPath, "utf8").replace(/\r\n/g, "\n") !== json ||
      !existsSync(reportPath) ||
      readFileSync(reportPath, "utf8").replace(/\r\n/g, "\n") !== report;
    if (stale) {
      console.error("error: the inventory is out of date: run node web/parity/api-inventory.mjs");
      return 1;
    }
    return 0;
  }
  writeFileSync(inventoryPath, json);
  writeFileSync(reportPath, report);
  console.log(`${inventory.counts.rows} rows, ${inventory.counts.classes} classes`);
  for (const [subtask, count] of Object.entries(inventory.counts.bySubtask)) {
    console.log(`  P3-3${subtask} ${DOMAINS[subtask]}: ${count}`);
  }
  if (removed.length) console.log(`removed rows: ${removed.join(", ")}`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}
