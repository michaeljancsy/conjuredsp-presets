# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Community preset library for ConjureDSP, an AUv3 audio effect plugin for macOS. Each preset is a standalone DSP script (Python or Rust) paired with a `_metadata.json` sidecar file. There is no build system, package manager, or test suite — the presets are loaded and executed by the ConjureDSP host app.

## Repo Layout

- `conjuredsp.json` — repo marker file (identifies this as a ConjureDSP preset repo)
- `python/` — Python preset scripts (`.py`) + metadata sidecars (`_metadata.json`)
- `rust/` — Rust preset scripts (`.rs`) + metadata sidecars (`_metadata.json`)

Each preset consists of two files, e.g. `python/slicer.py` + `python/slicer_metadata.json`.

## Preset Conventions

### Python presets
- Must define `process(inputs, outputs, frame_count, sample_rate, params)`.
- Declare parameters via a top-level `PARAMS` dict with rich metadata (min, max, unit, default, optional curve).
- `params` is keyed by parameter name (string), e.g. `params["rate"]`.
- May use `numpy`; must be real-time safe (no allocations in the processing loop).

### Rust presets
- Compiled to WebAssembly by the host. Must export: `get_input_ptr`, `get_output_ptr`, `get_params_ptr`, and `process`.
- Declare parameter metadata via a `METADATA` static (JSON string) and export `get_param_metadata_ptr`/`get_param_metadata_len`.
- Parameters accessed by index from `PARAMS_BUF`, e.g. `PARAMS_BUF[0]`.
- Use `#[no_mangle] pub extern "C"` on all exports. No std allocator — use static buffers.

### Metadata sidecar format
```json
{
  "name": "Display Name",
  "category": "Modulation",
  "author": "Author Name",
  "description": "Short description."
}
```

Valid categories: Utility, Distortion, Filter, Dynamics, Modulation, Delay, Generator.
