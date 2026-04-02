
from conjuredsp import db, mix, freq, toggle
from conjuredsp.nam import load_model
import numpy as np

PARAMS = {
    "input_gain": db(default=0),
    "output_level": db(default=0),
    "tone": freq(default=8000),
    "mix": mix(default=1.0),
}

model = load_model("tone3000://19/51")

# Simple one-pole lowpass for tone control
_prev = [0.0, 0.0]

def process(inputs, outputs, frame_count, sample_rate, params):
    global _prev
    in_gain = 10 ** (params["input_gain"] / 20.0)
    out_gain = 10 ** (params["output_level"] / 20.0)
    mix_val = params["mix"]

    # One-pole lowpass coefficient from tone knob
    fc = params["tone"]
    coeff = 1.0 - np.exp(-2.0 * np.pi * fc / sample_rate)

    for ch in range(len(inputs)):
        dry = inputs[ch][:frame_count]
        wet = model.process(dry * in_gain, ch)

        # Apply tone filter to wet signal
        for i in range(frame_count):
            _prev[ch] += coeff * (wet[i] - _prev[ch])
            wet[i] = _prev[ch]

        outputs[ch][:frame_count] = (dry * (1 - mix_val) + wet * mix_val) * out_gain
