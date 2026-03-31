
from conjuredsp import freq, db, mix, pct, time_ms, BiquadCoeffs, Biquad, DelayLine, LFO, soft_clip, db_to_gain, crossfade
import numpy as np

PARAMS = {
    "reverb": mix(default=0.65),
    "shimmer": pct(default=60),
    "drive": pct(default=40),
    "tone": freq(min=200, max=8000, default=2000),
    "mod_rate": freq(min=0.1, max=5.0, default=0.5),
    "mod_depth": pct(default=50),
    "decay": pct(default=75),
    "volume": db(default=0),
}

_state = None

def _init(sr, channels):
    max_samp = int(2.0 * sr)
    delays_ms = [29.7, 37.1, 41.3, 53.7]
    return {
        "delays": [[DelayLine(max_samp) for _ in delays_ms] for _ in range(channels)],
        "delay_samps": [d * 0.001 * sr for d in delays_ms],
        "lp_filters": [[Biquad() for _ in delays_ms] for _ in range(channels)],
        "hp_filter": [Biquad() for _ in range(channels)],
        "tone_filter": [Biquad() for _ in range(channels)],
        "lfo": LFO(sr, 0.5, "sine"),
        "lfo2": LFO(sr, 0.3, "triangle"),
    }

def process(inputs, outputs, frame_count, sample_rate, params):
    global _state
    if _state is None or len(_state["hp_filter"]) != len(inputs):
        _state = _init(sample_rate, len(inputs))
    s = _state

    mix_amt = params["reverb"]
    shimmer = params["shimmer"] / 100.0
    drive = 1.0 + (params["drive"] / 100.0) * 4.0
    tone = params["tone"]
    decay = 0.3 + (params["decay"] / 100.0) * 0.65
    vol = db_to_gain(params["volume"])

    s["lfo"].set_freq(params["mod_rate"])
    s["lfo2"].set_freq(params["mod_rate"] * 0.7)

    lp_coeffs = BiquadCoeffs.lowpass(tone, 0.707, sample_rate)
    hp_coeffs = BiquadCoeffs.highpass(120, 0.707, sample_rate)
    tone_coeffs = BiquadCoeffs.peak(3000, 0.8, shimmer * 6.0, sample_rate)

    for ch in range(len(inputs)):
        for f in s["lp_filters"][ch]:
            f.set_coeffs(lp_coeffs)
        s["hp_filter"][ch].set_coeffs(hp_coeffs)
        s["tone_filter"][ch].set_coeffs(tone_coeffs)

    mod_depth = params["mod_depth"] / 100.0

    for i in range(frame_count):
        mod1 = s["lfo"].tick() if i == 0 or True else s["lfo"].tick()
        mod2 = s["lfo2"].tick()

        for ch in range(len(inputs)):
            dry = inputs[ch][i]

            # Soft drive on input
            driven = soft_clip(dry, drive)

            # Read from delay network (FDN-style)
            taps = []
            for d_idx in range(4):
                base_delay = s["delay_samps"][d_idx]
                mod_offset = (mod1 if d_idx % 2 == 0 else mod2) * mod_depth * 30.0
                delay_time = base_delay + mod_offset
                tap = s["delays"][ch][d_idx].read(max(1.0, delay_time))
                tap = s["lp_filters"][ch][d_idx].process_sample(tap)
                taps.append(tap)

            # Hadamard-like mixing
            a, b, c, d = taps
            mixed = [
                (a + b + c + d) * 0.5,
                (a - b + c - d) * 0.5,
                (a + b - c - d) * 0.5,
                (a - b - c + d) * 0.5,
            ]

            # Write back with input
            for d_idx in range(4):
                s["delays"][ch][d_idx].write(driven * 0.3 + mixed[d_idx] * decay)

            # Sum reverb taps
            wet = sum(taps) * 0.25
            wet = s["hp_filter"][ch].process_sample(wet)
            wet = s["tone_filter"][ch].process_sample(wet)

            out = dry * (1.0 - mix_amt) + wet * mix_amt
            outputs[ch][i] = out * vol
