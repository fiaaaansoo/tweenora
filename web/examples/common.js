(function () {
  var params = new URLSearchParams(location.search);
  var baseTitle = document.title;
  var check = { state: "loading", error: null, frames: 0 };
  window.twnoCheck = check;

  function setState(state, text) {
    check.state = state;
    document.title = baseTitle + ": " + (text || state);
  }

  function fail(error) {
    check.error = String(error && error.data ? error.data : error);
    setState("error", check.error);
  }

  function configureRuntime() {
    rive.RuntimeLoader.setWasmUrl("/pkg/rive.wasm");
    rive.RuntimeLoader.setWasmFallbackUrl("/pkg/rive_fallback.wasm");
  }

  function withCanvas(parent, id) {
    var canvas = document.createElement("canvas");
    canvas.id = id;
    canvas.className = "small";
    parent.appendChild(canvas);
    return canvas;
  }

  function sizeCanvas(canvas) {
    var size = params.get("size");
    if (size) {
      canvas.className = "";
      canvas.style.width = size + "px";
      canvas.style.height = size + "px";
    }
  }

  function fetchBytes(url) {
    return fetch(url)
      .then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status + " for " + url); }
        return response.arrayBuffer();
      })
      .then(function (buffer) { return new Uint8Array(buffer); });
  }

  function countFrames() {
    check.frames += 1;
    if (check.state === "loaded") {
      setState("drawing");
    }
  }

  function start(run) {
    if (!params.get("file")) {
      fail("missing ?file=<url> parameter");
      return;
    }
    configureRuntime();
    run();
  }

  window.twnoExample = {
    start: start,
    sizeCanvas: sizeCanvas,
    fetchBytes: fetchBytes,
    params: params,
    file: params.get("file"),
    setState: setState,
    fail: fail,
    configureRuntime: configureRuntime,
    withCanvas: withCanvas,
    countFrames: countFrames,
  };
})();
