
from conjuredsp import db, mix, freq, toggle
from conjuredsp.nam import load_model
from conjuredsp import BiquadCoeffs, Biquad, db_to_gain, soft_clip

PARAMS = {
    "input": db(default=0),
    "output": db(default=0),
    "tone": freq(min=800, max=16000, default=6000),
    "drive": db(min=0, max=24, default=0),
    "mix": mix(default=1.0),
}

model = load_model("tone3000://44209/234539")
_filters = None

def process(inputs, outputs, frame_count, sample_rate, params):
    global _filters
    if _filters is None:
        _filters = [Biquad() for _ in range(len(inputs))]

    in_gain = db_to_gain(params["input"])
    out_gain = db_to_gain(params["output"])
    drive_gain = db_to_gain(params["drive"])
    mix_val = params["mix"]
    tone_freq = params["tone"]

    coeffs = BiquadCoeffs.lowpass(tone_freq, 0.707, sample_rate)

    for ch in range(len(inputs)):
        _filters[ch].set_coeffs(coeffs)
        dry = inputs[ch][:frame_count]
        driven = dry * in_gain * drive_gain
        wet = model.process(driven, ch)
        for i in range(frame_count):
            wet[i] = _filters[ch].process_sample(wet[i])
        outputs[ch][:frame_count] = (dry * (1 - mix_val) + wet * mix_val) * out_gain
