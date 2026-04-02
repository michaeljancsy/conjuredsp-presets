from conjuredsp.nam import load_model
from conjuredsp import db, mix

PARAMS = {
    "input_gain": db(default=0),
    "output_gain": db(default=0),
    "mix": mix(default=1.0),
}

model = load_model("tone3000://26/83293")

def process(inputs, outputs, frame_count, sample_rate, params):
    in_gain = 10 ** (params["input_gain"] / 20.0)
    out_gain = 10 ** (params["output_gain"] / 20.0)
    mix_val = params["mix"]
    for ch in range(len(inputs)):
        dry = inputs[ch][:frame_count]
        wet = model.process(dry * in_gain, ch)
        outputs[ch][:frame_count] = (dry * (1 - mix_val) + wet * mix_val) * out_gain
