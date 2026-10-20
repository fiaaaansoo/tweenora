(function () {
  "use strict";

  if (typeof rive === "undefined") {
    document.getElementById("error-text").textContent =
      "The animation engine could not be loaded (/pkg/rive.js). Build the package, then reload the page.";
    document.getElementById("error").hidden = false;
    document.getElementById("empty").hidden = true;
    return;
  }

  rive.Rive.suppressDeprecationWarnings = Object.values(rive.DeprecationKeys);

  var NONE = "";
  var TYPE_NUMBER = rive.StateMachineInputType.Number;
  var TYPE_TRIGGER = rive.StateMachineInputType.Trigger;
  var TYPE_BOOLEAN = rive.StateMachineInputType.Boolean;
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var webgl2 = null;

  var el = {};
  [
    "stage", "canvas", "empty", "loading", "loading-text", "error", "error-text", "error-details",
    "retry", "file-name", "file-input", "playbar", "play", "restart", "backdrop", "motion-note",
    "examples", "panel-empty", "panel-body", "artboard", "animation", "machine", "inputs",
    "properties", "live", "drop-veil", "examples-section", "empty-hint",
  ].forEach(function (id) { el[id] = document.getElementById(id); });

  var state = {
    bytes: null,
    instance: null,
    descriptor: null,
    attempt: null,
    contents: null,
    selection: { artboard: NONE, animation: NONE, machine: NONE },
    examples: [],
    fileToken: 0,
    instanceToken: 0,
    announceTimer: null,
    busyTimer: null,
    pending: null,
  };

  var CONTROL_LABELS = { number: "number", string: "text", boolean: "boolean", color: "color", enumType: "enum", trigger: "trigger" };
  var UNREADABLE = "Unrecognized or corrupted file, or an unsupported version.";

  function announce(text) {
    window.clearTimeout(state.announceTimer);
    state.announceTimer = window.setTimeout(function () { el.live.textContent = text; }, 250);
  }

  function track(name, data) {
    console.info("[demo]", name, data || {});
  }

  function create(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function show(node, visible) { node.hidden = !visible; }

  function setBusy(busy, text) {
    window.clearTimeout(state.busyTimer);
    el.stage.setAttribute("aria-busy", String(busy));
    if (busy) {
      el["loading-text"].textContent = text;
      state.busyTimer = window.setTimeout(function () { show(el.loading, true); }, 300);
    } else {
      show(el.loading, false);
    }
  }

  function showError(cause, details) {
    window.clearTimeout(state.announceTimer);
    el.live.textContent = "";
    setBusy(false);
    el["error-text"].textContent = cause;
    el["error-details"].textContent = details || "";
    show(el.error, true);
    show(el.empty, false);
    el.stage.classList.toggle("is-empty", !state.instance);
    track("demo_error", { cause: cause });
  }

  function hideError() {
    var active = document.activeElement;
    if (active && (el.error.contains(active) || el.empty.contains(active))) { el["file-name"].focus(); }
    show(el.error, false);
    show(el.empty, !state.instance);
  }

  function extensionOf(name) {
    var match = /\.(twno|riv)$/i.exec(name);
    return match ? match[1].toLowerCase() : null;
  }

  function hasWebGL2() {
    if (webgl2 === null) {
      try {
        var context = document.createElement("canvas").getContext("webgl2");
        webgl2 = Boolean(context);
        if (context) {
          var lose = context.getExtension("WEBGL_lose_context");
          if (lose) { lose.loseContext(); }
        }
      } catch (error) {
        webgl2 = false;
      }
    }
    return webgl2;
  }

  function validate(bytes) {
    return new Promise(function (resolve, reject) {
      var file = new rive.RiveFile({
        buffer: bytes,
        onLoad: function () { file.cleanup(); resolve(); },
        onLoadError: function (event) {
          reject(new Error(String(event && event.data ? event.data : "load error")));
          try { file.cleanup(); } catch (error) { return; }
        },
      });
      file.init().catch(reject);
    });
  }

  function openFile(descriptor, kind) {
    var token = ++state.fileToken;
    state.instanceToken += 1;
    state.pending = null;
    state.attempt = descriptor;
    hideError();
    setBusy(false);
    if (kind !== "example" && kind !== "retry") { clearExampleMarks(); }
    if (!extensionOf(descriptor.name)) {
      showError("Unsupported format: only .twno and .riv files can be opened.", descriptor.name);
      return;
    }
    if (!hasWebGL2()) {
      showError("WebGL2 is not available in this browser: the animation cannot be displayed.", "getContext('webgl2') returned null");
      return;
    }
    var started = performance.now();
    setBusy(true, "Loading \"" + descriptor.name + "\"…");
    announce("Loading \"" + descriptor.name + "\"…");
    descriptor.load().then(function (bytes) {
      if (token !== state.fileToken) { return null; }
      return validate(bytes).then(function () { return bytes; });
    }).then(function (bytes) {
      if (bytes === null || token !== state.fileToken) { return null; }
      return openInstance(bytes, descriptor, { artboard: NONE, animation: NONE, machine: NONE }, descriptor.hint || {}, true)
        .then(function (committed) {
          if (committed) {
            track("demo_loaded", { source: kind, ext: extensionOf(descriptor.name), ms: Math.round(performance.now() - started) });
          }
        });
    }).catch(function (error) {
      if (token === state.fileToken) { failOpening(error); }
    }).then(function () {
      if (token === state.fileToken) { setBusy(false); }
    });
  }

  function openInstance(bytes, descriptor, selection, hint, initial) {
    var token = ++state.instanceToken;
    return new Promise(function (resolve, reject) {
      var wanted = initial ? Object.assign({}, selection, hint) : selection;
      var options = {
        buffer: bytes,
        canvas: el.canvas,
        autoplay: !reducedMotion,
        autoBind: true,
        onLoad: function () {
          if (token !== state.instanceToken) { instance.cleanup(); resolve(false); return; }
          try {
            var again = commit(instance, bytes, descriptor, wanted, initial);
            if (again) {
              instance.cleanup();
              openInstance(bytes, descriptor, again, null, false).then(resolve, reject);
              return;
            }
            resolve(true);
          } catch (error) {
            instance.cleanup();
            if (state.instance === instance) { resetToEmpty(); }
            reject(error);
          }
        },
        onLoadError: function (event) {
          if (token !== state.instanceToken) { resolve(false); return; }
          reject(new Error(String(event && event.data ? event.data : "load error")));
        },
      };
      if (wanted.artboard) { options.artboard = wanted.artboard; }
      if (wanted.machine) { options.stateMachine = wanted.machine; }
      else if (wanted.animation) { options.animations = wanted.animation; }
      var instance = new rive.Rive(options);
    });
  }

  function resetToEmpty() {
    if (state.instance) { state.instance.cleanup(); }
    state.instance = null;
    state.bytes = null;
    state.descriptor = null;
    state.contents = null;
    state.pending = null;
    state.selection = { artboard: NONE, animation: NONE, machine: NONE };
    show(el.canvas, false);
    show(el.playbar, false);
    show(el["panel-body"], false);
    show(el["panel-empty"], true);
    el["file-name"].textContent = "No file";
    el.stage.classList.add("is-empty");
  }

  function defaultSelection(entry, artboard, chosen) {
    var machine = chosen.machine;
    var animation = chosen.animation;
    if (!machine && !animation) {
      if (entry.stateMachines.length) { machine = entry.stateMachines[0].name; }
      else if (entry.animations.length) { animation = entry.animations[0]; }
    }
    return { artboard: artboard, animation: animation || NONE, machine: machine || NONE };
  }

  function commit(instance, bytes, descriptor, wanted, initial) {
    var contents = instance.contents.artboards || [];
    var artboard = instance.activeArtboard;
    var entry = contents.filter(function (item) { return item.name === artboard; })[0] || { animations: [], stateMachines: [] };
    var selection = initial ? defaultSelection(entry, artboard, wanted) : { artboard: artboard, animation: wanted.animation, machine: wanted.machine };
    if (initial && (selection.machine !== wanted.machine || selection.animation !== wanted.animation)) {
      return selection;
    }
    if (state.instance && state.instance !== instance) { state.instance.cleanup(); }
    state.pending = null;
    state.bytes = bytes;
    state.descriptor = descriptor;
    state.contents = contents;
    state.selection = selection;
    state.instance = instance;
    show(el.canvas, true);
    instance.resizeDrawingSurfaceToCanvas();
    show(el.empty, false);
    el.stage.classList.remove("is-empty");
    hideError();
    el["file-name"].textContent = descriptor.name;
    el.canvas.setAttribute("aria-label", "Preview of \"" + descriptor.name + "\", artboard \"" + artboard + "\"");
    fillSelects(entry);
    buildInputs();
    buildProperties();
    show(el["panel-empty"], false);
    show(el["panel-body"], true);
    show(el.playbar, true);
    show(el["motion-note"], reducedMotion);
    bindPlayback();
    setBusy(false);
    announce(
      "\"" + descriptor.name + "\" loaded: " + plural(contents.length, "artboard") + ", " +
      plural(entry.animations.length, "animation") + ", " + plural(entry.stateMachines.length, "state machine") + "."
    );
    return null;
  }

  function failOpening(error) {
    state.pending = null;
    var message = String(error && error.message ? error.message : error);
    var network = /^HTTP |Failed to fetch|NetworkError/.test(message);
    showError(network ? "The file could not be downloaded." : UNREADABLE, message);
  }

  function clearExampleMarks() {
    Array.prototype.forEach.call(el.examples.querySelectorAll(".card"), function (card) { card.removeAttribute("aria-current"); });
    try { history.replaceState(null, "", location.pathname + location.search); } catch (error) { return; }
  }

  function plural(count, word) { return count + " " + word + (count > 1 ? "s" : ""); }

  function fillOptions(select, values, current, emptyLabel) {
    select.textContent = "";
    if (emptyLabel) {
      var none = create("option", "", emptyLabel);
      none.value = NONE;
      select.appendChild(none);
    }
    values.forEach(function (value) {
      var option = create("option", "", value);
      option.value = value;
      select.appendChild(option);
    });
    select.value = current;
    select.disabled = !values.length;
  }

  function fillSelects(entry) {
    fillOptions(el.artboard, state.contents.map(function (item) { return item.name; }), state.selection.artboard);
    fillOptions(el.animation, entry.animations, state.selection.animation, entry.animations.length ? "None" : "No animation in this artboard");
    fillOptions(el.machine, entry.stateMachines.map(function (item) { return item.name; }), state.selection.machine, entry.stateMachines.length ? "None" : "No state machine in this artboard");
  }

  function changeSelection(change) {
    if (!state.bytes || el.stage.getAttribute("aria-busy") === "true") { return; }
    var next = Object.assign({}, state.pending || state.selection, change);
    if (change.animation) { next.machine = NONE; }
    if (change.machine) { next.animation = NONE; }
    if (change.artboard) { next.animation = NONE; next.machine = NONE; }
    state.pending = next;
    openInstance(state.bytes, state.descriptor, next, null, false).catch(failOpening);
  }

  function groupTitle(text) { return create("h3", "group-title", text); }

  function controlShell(name, typeLabel) {
    var shell = create("div", "control");
    var head = create("div", "control-head");
    head.appendChild(create("strong", "", name));
    head.appendChild(create("span", "muted", typeLabel));
    shell.appendChild(head);
    return shell;
  }

  function triggerButton(shell, label, fire) {
    var status = create("span", "status-text");
    var button = create("button", "btn", "Fire");
    button.type = "button";
    button.setAttribute("aria-label", "Fire " + label);
    button.addEventListener("click", function () {
      fire();
      status.textContent = "Fired";
      window.setTimeout(function () { status.textContent = ""; }, 1000);
      announce("Trigger \"" + label + "\" fired.");
    });
    shell.appendChild(button);
    shell.appendChild(status);
  }

  function switchRow(label, checked, onChange) {
    var row = create("label", "switch-row");
    row.appendChild(create("span", "", "On"));
    var box = create("input");
    box.type = "checkbox";
    box.setAttribute("role", "switch");
    box.setAttribute("aria-label", label);
    box.checked = Boolean(checked);
    box.addEventListener("change", function () { onChange(box.checked); });
    row.appendChild(box);
    return row;
  }

  function numberField(label, value, onChange) {
    var field = create("input");
    field.type = "number";
    field.step = "any";
    field.inputMode = "decimal";
    field.value = String(value);
    field.setAttribute("aria-label", label);
    field.addEventListener("input", function () {
      var parsed = Number(field.value);
      var valid = field.value !== "" && isFinite(parsed);
      field.setAttribute("aria-invalid", String(!valid));
      if (valid) { onChange(parsed); }
    });
    return field;
  }

  function buildInputs() {
    var host = el.inputs;
    host.textContent = "";
    var list = state.selection.machine ? (state.instance.stateMachineInputs(state.selection.machine) || []) : [];
    if (!list.length) {
      host.appendChild(create("p", "muted", "This state machine has no inputs."));
      return;
    }
    list.forEach(function (input) {
      var shell;
      if (input.type === TYPE_BOOLEAN) {
        shell = controlShell(input.name, "boolean");
        shell.appendChild(switchRow(input.name, input.value, function (checked) {
          input.value = checked;
          track("input_changed", { type: "boolean" });
        }));
      } else if (input.type === TYPE_NUMBER) {
        shell = controlShell(input.name, "number");
        shell.appendChild(numberField(input.name, input.value, function (value) {
          input.value = value;
          track("input_changed", { type: "number" });
        }));
      } else if (input.type === TYPE_TRIGGER) {
        shell = controlShell(input.name, "trigger");
        triggerButton(shell, input.name, function () { input.fire(); track("input_changed", { type: "trigger" }); });
      }
      if (shell) { host.appendChild(shell); }
    });
  }

  function toHex(value) {
    return "#" + ("000000" + (value & 0xffffff).toString(16)).slice(-6);
  }

  function fromHex(text) {
    var match = /^#?([0-9a-f]{6})$/i.exec(text.trim());
    if (!match) { return null; }
    var number = parseInt(match[1], 16);
    return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
  }

  function colorControl(shell, label, color) {
    var row = create("div", "color-row");
    var swatch = create("input");
    swatch.type = "color";
    swatch.value = toHex(color.value);
    swatch.setAttribute("aria-label", label + ": color picker");
    var hex = create("input", "hex");
    hex.type = "text";
    hex.value = toHex(color.value);
    hex.setAttribute("aria-label", label + ": hexadecimal value");
    function apply(parts) {
      var alpha = (color.value >>> 24) & 255;
      if (typeof color.argb === "function") { color.argb(alpha, parts[0], parts[1], parts[2]); }
      else { color.rgb(parts[0], parts[1], parts[2]); }
      track("input_changed", { type: "color" });
    }
    swatch.addEventListener("input", function () {
      hex.value = swatch.value;
      hex.removeAttribute("aria-invalid");
      apply(fromHex(swatch.value));
    });
    hex.addEventListener("input", function () {
      var parts = fromHex(hex.value);
      hex.setAttribute("aria-invalid", String(!parts));
      if (parts) { swatch.value = toHex((parts[0] << 16) | (parts[1] << 8) | parts[2]); apply(parts); }
    });
    row.appendChild(swatch);
    row.appendChild(hex);
    shell.appendChild(row);
  }

  function propertyControl(vmi, entry, prefix) {
    var kind = entry.type;
    var name = entry.name;
    var label = prefix ? prefix + " " + name : name;
    var shell = controlShell(name, CONTROL_LABELS[kind] || kind);
    if (kind === "number") {
      var number = vmi.number(name);
      shell.appendChild(numberField(label, number.value, function (value) { number.value = value; track("input_changed", { type: "number" }); }));
    } else if (kind === "string") {
      var text = vmi.string(name);
      var field = create("input");
      field.type = "text";
      field.value = text.value;
      field.setAttribute("aria-label", label);
      field.addEventListener("input", function () { text.value = field.value; track("input_changed", { type: "string" }); });
      shell.appendChild(field);
    } else if (kind === "boolean") {
      var flag = vmi.boolean(name);
      shell.appendChild(switchRow(label, flag.value, function (checked) { flag.value = checked; track("input_changed", { type: "boolean" }); }));
    } else if (kind === "color") {
      colorControl(shell, label, vmi.color(name));
    } else if (kind === "enumType") {
      var choice = vmi.enum(name);
      var select = create("select");
      select.setAttribute("aria-label", label);
      choice.values.forEach(function (value) {
        var option = create("option", "", value);
        option.value = value;
        select.appendChild(option);
      });
      select.value = choice.value;
      select.addEventListener("change", function () { choice.value = select.value; track("input_changed", { type: "enum" }); });
      shell.appendChild(select);
    } else if (kind === "trigger") {
      var trigger = vmi.trigger(name);
      triggerButton(shell, label, function () { trigger.trigger(); track("input_changed", { type: "trigger" }); });
    } else {
      shell.appendChild(create("p", "muted", "Not editable in this demo."));
    }
    return shell;
  }

  function fillProperties(host, vmi, depth, prefix) {
    vmi.properties.forEach(function (entry) {
      if (entry.type === "viewModel") {
        try {
          var child = vmi.viewModel(entry.name);
          if (child && depth < 4) {
            host.appendChild(groupTitle(entry.name));
            fillProperties(host, child, depth + 1, entry.name);
          }
        } catch (error) {
          var group = controlShell(entry.name, entry.type);
          group.appendChild(create("p", "muted", "Not editable in this demo."));
          host.appendChild(group);
        }
        return;
      }
      try {
        host.appendChild(propertyControl(vmi, entry, prefix));
      } catch (error) {
        var broken = controlShell(entry.name, entry.type);
        broken.appendChild(create("p", "muted", "Not editable in this demo."));
        host.appendChild(broken);
      }
    });
  }

  function buildProperties() {
    var host = el.properties;
    host.textContent = "";
    var vmi = null;
    var properties = [];
    try {
      vmi = state.instance.viewModelInstance;
      properties = vmi ? vmi.properties : [];
    } catch (error) {
      vmi = null;
    }
    if (!vmi || !properties.length) {
      host.appendChild(create("p", "muted", "This file has no view model."));
      return;
    }
    if (!state.selection.machine) {
      host.appendChild(create("p", "help", "Properties only affect the drawing when a state machine is selected."));
    }
    fillProperties(host, vmi, 0, "");
  }

  function updatePlayButton() {
    el.play.textContent = state.instance && state.instance.isPlaying ? "Pause" : "Play";
  }

  function bindPlayback() {
    [rive.EventType.Play, rive.EventType.Pause, rive.EventType.Stop].forEach(function (type) {
      state.instance.on(type, updatePlayButton);
    });
    updatePlayButton();
  }

  function togglePlay() {
    var instance = state.instance;
    if (!instance) { return; }
    if (instance.isPlaying) {
      instance.pause();
    } else {
      var name = state.selection.machine || state.selection.animation;
      if (name) { instance.play(name); } else { instance.play(); }
    }
    updatePlayButton();
  }

  function fetchDescriptor(url, name, hint) {
    return {
      name: name,
      hint: hint,
      load: function () {
        return fetch(url).then(function (response) {
          if (!response.ok) { throw new Error("HTTP " + response.status + " for " + url); }
          return response.arrayBuffer();
        }).then(function (buffer) { return new Uint8Array(buffer); });
      },
    };
  }

  function fileDescriptor(file) {
    return {
      name: file.name,
      hint: {},
      load: function () { return file.arrayBuffer().then(function (buffer) { return new Uint8Array(buffer); }); },
    };
  }

  function renderExamples(list) {
    state.examples = list;
    show(el["examples-section"], list.length > 0);
    show(el["empty-hint"], list.length > 0);
    list.forEach(function (item) {
      var entry = create("li");
      var card = create("button", "card");
      card.type = "button";
      card.dataset.id = item.id;
      card.appendChild(create("span", "title", item.title));
      card.appendChild(create("span", "desc", item.description));
      card.appendChild(create("span", "pill", /\.riv$/.test(item.file) ? ".riv" : ".twno"));
      card.addEventListener("click", function () { openExample(item); });
      entry.appendChild(card);
      el.examples.appendChild(entry);
    });
  }

  function openExample(item) {
    Array.prototype.forEach.call(el.examples.querySelectorAll(".card"), function (card) {
      if (card.dataset.id === item.id) { card.setAttribute("aria-current", "true"); }
      else { card.removeAttribute("aria-current"); }
    });
    try { history.replaceState(null, "", "#example=" + item.id); } catch (error) { track("hash_unavailable"); }
    var hint = { artboard: item.artboard || NONE, machine: item.stateMachine || NONE, animation: item.animation || NONE };
    openFile(fetchDescriptor(item.file, item.file.split("/").pop(), hint), "example");
  }

  function loadExampleFromHash() {
    var match = /#example=([\w-]+)/.exec(location.hash);
    if (!match) { return; }
    var item = state.examples.filter(function (entry) { return entry.id === match[1]; })[0];
    if (item) { openExample(item); }
  }

  function setTheme(theme) {
    if (theme === "auto") { document.documentElement.removeAttribute("data-theme"); }
    else { document.documentElement.setAttribute("data-theme", theme); }
    Array.prototype.forEach.call(document.querySelectorAll(".theme button"), function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.theme === theme));
    });
    try { localStorage.setItem("tweenora-theme", theme); } catch (error) { return; }
  }

  function restoreTheme() {
    var saved = null;
    try { saved = localStorage.getItem("tweenora-theme"); } catch (error) { saved = null; }
    setTheme(saved === "light" || saved === "dark" ? saved : "auto");
  }

  function hasFiles(event) {
    return Array.prototype.indexOf.call((event.dataTransfer && event.dataTransfer.types) || [], "Files") >= 0;
  }

  function wire() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-open]"), function (button) {
      button.addEventListener("click", function () { el["file-input"].click(); });
    });
    el["file-input"].addEventListener("change", function () {
      var file = el["file-input"].files[0];
      if (file) { openFile(fileDescriptor(file), "browse"); }
      el["file-input"].value = "";
    });
    el.play.addEventListener("click", togglePlay);
    el.restart.addEventListener("click", function () { changeSelection({}); });
    el.backdrop.addEventListener("change", function () { el.stage.dataset.backdrop = el.backdrop.value; });
    el.artboard.addEventListener("change", function () { changeSelection({ artboard: el.artboard.value }); });
    el.animation.addEventListener("change", function () { changeSelection({ animation: el.animation.value }); });
    el.machine.addEventListener("change", function () { changeSelection({ machine: el.machine.value }); });
    window.addEventListener("hashchange", loadExampleFromHash);
    el.retry.addEventListener("click", function () { if (state.attempt) { openFile(state.attempt, "retry"); } });
    Array.prototype.forEach.call(document.querySelectorAll(".theme button"), function (button) {
      button.addEventListener("click", function () { setTheme(button.dataset.theme); });
    });
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(function () {
        if (state.instance) { state.instance.resizeDrawingSurfaceToCanvas(); }
      }).observe(el.stage);
    }
    var depth = 0;
    window.addEventListener("dragenter", function (event) {
      if (!hasFiles(event)) { return; }
      depth += 1;
      show(el["drop-veil"], true);
      el.stage.classList.add("is-dragging");
    });
    window.addEventListener("dragleave", function (event) {
      if (!hasFiles(event)) { return; }
      depth = Math.max(0, depth - 1);
      if (!depth) { show(el["drop-veil"], false); el.stage.classList.remove("is-dragging"); }
    });
    window.addEventListener("dragover", function (event) { if (hasFiles(event)) { event.preventDefault(); } });
    window.addEventListener("drop", function (event) {
      if (!hasFiles(event)) { return; }
      event.preventDefault();
      depth = 0;
      show(el["drop-veil"], false);
      el.stage.classList.remove("is-dragging");
      var file = event.dataTransfer.files[0];
      if (file) { openFile(fileDescriptor(file), "drop"); }
    });
  }

  window.tweenoraDemo = {
    state: function () {
      return {
        file: state.descriptor && state.descriptor.name,
        selection: state.selection,
        artboards: state.contents ? state.contents.length : 0,
        inputs: el.inputs.querySelectorAll(".control").length,
        properties: el.properties.querySelectorAll(".control").length,
        playing: state.instance ? state.instance.isPlaying : null,
        error: el.error.hidden ? null : el["error-text"].textContent,
        loaded: Boolean(state.instance),
      };
    },
    instance: function () { return state.instance; },
  };

  restoreTheme();
  wire();
  el.stage.dataset.backdrop = "checker";
  el.stage.classList.add("is-empty");
  fetch("examples.json").then(function (response) { return response.json(); }).then(function (list) {
    renderExamples(list);
    loadExampleFromHash();
  }).catch(function () {
    show(el["examples-section"], true);
    el.examples.appendChild(create("li", "muted", "The examples list could not be loaded."));
  });
})();
