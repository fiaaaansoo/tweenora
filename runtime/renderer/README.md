# Tweenora Renderer

The Tweenora Renderer is a vector and raster graphics renderer custom-built for Tweenora content, for animation, and for runtime.

This directory contains the renderer code and an example for how to interface with it directly. It contains the best in class concrete implementation of Tweenora's rendering abstraction layer, which we call the Tweenora Renderer.

## Clone the repo

```
git clone https://github.com/fiaaaansoo/tweenora.git
cd tweenora/runtime/renderer
```

## Add build_rive.sh to $PATH

```
export PATH="$PATH:$(realpath ../build)"
```

## Build & run

```
build_rive.sh release
out/release/path_fiddle [/path/to/my.twno]
```

## Build & serve for WebGL2

```
build_rive.sh ninja wasm release
cd out/wasm_release
python3 -m http.server 5555
```

## Helpful keys

- `h`/`H`: add/subtract copies to the left and right (only when a .twno or .riv is provided)
- `j`/`J`: add/subtract copies below (only when a .twno or .riv is provided)
- `k`/`K`: add/subtract copies above (only when a .twno or .riv is provided)
- `p`: pause runtime (for benchmarking the renderer in isolation)
- `a`: toggle "atomic" mode
