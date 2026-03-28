from conjuredsp import pct, db
from conjuredsp.dsp import db_to_gain, smooth_coeff
from conjuredsp.filters import Biquad, BiquadCoeffs
from math import tanh

PARAMS = {
    "drive": pct(),       # Gain / distortion amount
    "tone": pct(),        # Brightness
    "bass": db(),         # Low EQ
    "mids": db(),         # Mid bark
    "presence": db(),     # Upper-mid bite
    "tight": pct(),       # Pre-distortion low cut
    "output": db(),       # Output level
}

_state = None

def _init(sr):
    s = {'sr': sr, 'ch': []}
    for _ in range(2):
        c = {
            # Input high-pass — tightens lows before distortion
            'hp': Biquad(BiquadCoeffs.highpass(100.0, 0.707, sr)),
            # Pre-gain mid emphasis — the Marshall "bark"
            'pre_mid': Biquad(BiquadCoeffs.peak(900.0, 1.5, 6.0, sr)),
            # Inter-stage scoop for note definition
            'inter_scoop': Biquad(BiquadCoeffs.peak(450.0, 0.7, -2.0, sr)),
            # Inter-stage LP to tame fizz between stages
            'inter_lp': Biquad(BiquadCoeffs.lowpass(6000.0, 0.707, sr)),
            # Post-distortion tone stack
            'eq_bass': Biquad(BiquadCoeffs.lowshelf(200.0, 0.707, 0.0, sr)),
            'eq_mids': Biquad(BiquadCoeffs.peak(1000.0, 1.5, 3.0, sr)),
            'eq_pres': Biquad(BiquadCoeffs.peak(3200.0, 1.8, 2.0, sr)),
            # Cabinet simulation (4x12 w/ V30-style response)
            'cab_hp': Biquad(BiquadCoeffs.highpass(75.0, 0.707, sr)),
            'cab_scoop': Biquad(BiquadCoeffs.peak(400.0, 0.8, -1.5, sr)),
            'cab_peak': Biquad(BiquadCoeffs.peak(2500.0, 2.0, 3.0, sr)),
            'cab_lp': Biquad(BiquadCoeffs.lowpass(5500.0, 0.6, sr)),
            # State
            'gate_env': 0.0,
            'sm_drive': 20.0,
        }
        s['ch'].append(c)
    s['gate_att'] = smooth_coeff(0.1, sr)
    s['gate_rel'] = smooth_coeff(80.0, sr)
    s['p_sm'] = smooth_coeff(5.0, sr)
    return s

def process(inputs, outputs, frame_count, sample_rate, params):
    global _state
    if _state is None or _state['sr'] != sample_rate:
        _state = _init(sample_rate)

    sr = sample_rate
    st = _state

    dp = params["drive"] / 100.0
    tp = params["tone"] / 100.0
    out_g = db_to_gain(params["output"])

    # Exponential drive curve — 50% default lands in punk crunch territory
    drive = 4.0 + (dp ** 1.5) * 46.0

    # Tightness: HP cutoff before distortion (60–200 Hz)
    hp_f = 60.0 + (params["tight"] / 100.0) * 140.0

    # Tone knob controls cabinet brightness
    cab_lp_f = 3500.0 + tp * 4000.0

    gate_th = 0.005

    n_ch = min(len(inputs), len(outputs), 2)
    for ch in range(n_ch):
        c = st['ch'][ch]
        inp = inputs[ch]
        out = outputs[ch]

        # Update variable filters
        c['hp'].set_coeffs(BiquadCoeffs.highpass(hp_f, 0.707, sr))
        c['eq_bass'].set_coeffs(BiquadCoeffs.lowshelf(200.0, 0.707, params["bass"], sr))
        c['eq_mids'].set_coeffs(BiquadCoeffs.peak(1000.0, 1.5, params["mids"] + 3.0, sr))
        c['eq_pres'].set_coeffs(BiquadCoeffs.peak(3200.0, 1.8, params["presence"] + 2.0, sr))
        c['cab_lp'].set_coeffs(BiquadCoeffs.lowpass(cab_lp_f, 0.6, sr))

        gate_att = st['gate_att']
        gate_rel = st['gate_rel']
        p_sm = st['p_sm']
        gate_env = c['gate_env']
        sm_d = c['sm_drive']

        for i in range(frame_count):
            x = float(inp[i])

            # ---- Noise gate ----
            ae = abs(x)
            if ae > gate_env:
                gate_env = gate_att * gate_env + (1.0 - gate_att) * ae
            else:
                gate_env = gate_rel * gate_env + (1.0 - gate_rel) * ae
            if gate_env < gate_th:
                x *= (gate_env / gate_th) ** 2

            # Smooth drive to avoid zipper noise
            sm_d = p_sm * sm_d + (1.0 - p_sm) * drive

            # ---- Input HP (tightness) ----
            x = c['hp'].process_sample(x)

            # ---- Pre-emphasis: mid bark ----
            x = c['pre_mid'].process_sample(x)

            # ---- Stage 1: initial breakup ----
            x = tanh(x * sm_d * 0.175)

            # ---- Inter-stage shaping ----
            x = c['inter_scoop'].process_sample(x)

            # ---- Stage 2: main crunch ----
            x = tanh(x * sm_d * 0.12)

            # ---- Inter-stage HF taming ----
            x = c['inter_lp'].process_sample(x)

            # ---- Stage 3: final saturation (asymmetric = tube character) ----
            x2 = x * 2.0
            if x2 > 0:
                x = tanh(x2 * 1.15)
            else:
                x = tanh(x2 * 0.85)

            # ---- Tone stack ----
            x = c['eq_bass'].process_sample(x)
            x = c['eq_mids'].process_sample(x)
            x = c['eq_pres'].process_sample(x)

            # ---- Cabinet sim ----
            x = c['cab_hp'].process_sample(x)
            x = c['cab_scoop'].process_sample(x)
            x = c['cab_peak'].process_sample(x)
            x = c['cab_lp'].process_sample(x)

            out[i] = x * out_g

        c['gate_env'] = gate_env
        c['sm_drive'] = sm_d
