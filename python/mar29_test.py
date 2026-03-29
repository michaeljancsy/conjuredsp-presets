
from conjuredsp import freq, db, pct, mix, toggle, time_ms, param
import pedalboard
import numpy as np

PARAMS = {
    "drive": pct(default=60),
    "tone": freq(min=1000, max=16000, default=4000),
    "chorus_rate": param(0.1, 5.0, default=1.2, unit="Hz"),
    "chorus_depth": pct(default=60),
    "reverb_size": pct(default=80),
    "reverb_damping": pct(default=70),
    "shimmer": pct(default=30),
    "mix": mix(default=0.75),
}

_board = None
_prev_params = {}

def _build_board(sample_rate, params):
    drive = params["drive"] / 100.0
    tone = params["tone"]
    chorus_rate = params["chorus_rate"]
    chorus_depth = params["chorus_depth"] / 100.0
    reverb_size = params["reverb_size"] / 100.0
    reverb_damping = params["reverb_damping"] / 100.0
    shimmer = params["shimmer"] / 100.0

    board = pedalboard.Pedalboard([
        # Soft clipping drive
        pedalboard.Gain(gain_db=drive * 30),
        pedalboard.Distortion(drive_db=drive * 20),

        # Tone control — roll off highs
        pedalboard.LowpassFilter(cutoff_frequency_hz=tone),

        # Lush chorus for detuned shimmer
        pedalboard.Chorus(
            rate_hz=chorus_rate,
            depth=chorus_depth,
            mix=0.5 + shimmer * 0.4,
            feedback=0.3,
        ),

        # Massive reverb wash
        pedalboard.Reverb(
            room_size=reverb_size,
            damping=reverb_damping,
            wet_level=0.6 + shimmer * 0.3,
            dry_level=0.3,
            width=1.0,
        ),
    ], sample_rate=sample_rate)
    return board

def process(inputs, outputs, frame_count, sample_rate, params):
    global _board, _prev_params

    if _board is None or params != _prev_params:
        _board = _build_board(sample_rate, params)
        _prev_params = dict(params)

    wet_mix = params["mix"]
    dry_mix = 1.0 - wet_mix

    # Stack channels into (channels, samples) array
    audio = np.stack([ch[:frame_count] for ch in inputs])
    wet = _board(audio, sample_rate)

    for ch in range(len(inputs)):
        outputs[ch][:frame_count] = dry_mix * inputs[ch][:frame_count] + wet_mix * wet[ch]
