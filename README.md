# ConjureDSP Community Presets

Community preset library for [ConjureDSP](https://github.com/michaeljancsy/ConjureDSP) — an AUv3 audio effect plugin for macOS with Python and Rust DSP scripting.

## Browsing Presets

Open ConjureDSP in any DAW, click the preset dropdown, and select **Browse Community...** to browse and install presets directly from this repo.

You can also import any preset by URL: click **Import from URL...** in the preset dropdown and paste a raw GitHub link.

## Repo Structure

This repo follows the [ConjureDSP Preset Repo Format](https://github.com/michaeljancsy/ConjureDSP/blob/main/docs/preset-repo-format.md):

```
conjuredsp.json                  ← repo marker
python/                        ← Python presets
  slicer.py                    ← preset script
  slicer_metadata.json         ← name, category, author, description
rust/                          ← Rust presets
  slicer.rs
  slicer_metadata.json
```

## Contributing

1. Fork this repo
2. Add your preset script to `python/` or `rust/`
3. Add a `<name>_metadata.json` sidecar next to it:
   ```json
   {
     "name": "My Effect",
     "category": "Modulation",
     "author": "Your Name",
     "description": "Short description of what it does."
   }
   ```
4. Open a pull request

### Preset Guidelines

- **Python presets** must define a `process(inputs, outputs, frame_count, sample_rate, params)` function
- **Rust presets** must define `get_input_ptr`, `get_output_ptr`, `get_params_ptr`, and `process` exports
- Declare rich parameter metadata via `PARAMS` dict (Python) or `METADATA` static + `get_param_metadata_json`/`get_param_metadata_len` exports (Rust) for named parameters with real ranges, units, and optional log curve mapping
- Keep presets real-time safe: no allocations in the processing loop

## Categories

| Category | Description |
|----------|-------------|
| Utility | Passthrough, gain, DC blocking, stereo tools |
| Distortion | Clipping, waveshaping, bitcrushing |
| Filter | Low-pass, high-pass, state variable filters |
| Dynamics | Compression, limiting, gating |
| Modulation | Tremolo, chorus, flanger, phaser, ring mod |
| Delay | Simple delay, ping-pong, slicer |
| Generator | Noise generators, oscillators |
