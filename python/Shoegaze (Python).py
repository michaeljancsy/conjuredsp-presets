
from conjuredsp import freq, pct, mix, param, toggle, BiquadCoeffs, Biquad, DelayLine, LFO, soft_clip, db_to_gain, ms_to_samples
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

# Persistent state
_tone_filters = None
_chorus_delays = None
_chorus_lfos = None
_reverb_delays = None
_reverb_lpfs = None
_allpass_delays = None
_initialized = False

def _init(sample_rate, channels):
    global _tone_filters, _chorus_delays, _chorus_lfos
    global _reverb_delays, _reverb_lpfs, _allpass_delays, _initialized

    _tone_filters = [Biquad() for _ in range(channels)]

    # Chorus: 2 voices per channel with slightly different rates
    _chorus_delays = [[DelayLine(int(0.05 * sample_rate)) for _ in range(2)] for _ in range(channels)]
    _chorus_lfos = [
        [LFO(sample_rate, 1.0, "sine"), LFO(sample_rate, 1.0, "triangle")]
        for _ in range(channels)
    ]

    # Reverb: 4 parallel comb filters + 2 series allpass per channel
    comb_lengths_ms = [29.7, 37.1, 41.1, 43.7]
    allpass_lengths_ms = [5.0, 1.7]
    _reverb_delays = [
        [DelayLine(int(t * 0.001 * sample_rate * 2.5)) for t in comb_lengths_ms]
        for _ in range(channels)
    ]
    _reverb_lpfs = [[Biquad() for _ in range(4)] for _ in range(channels)]
    _allpass_delays = [
        [DelayLine(int(t * 0.001 * sample_rate * 2.5)) for t in allpass_lengths_ms]
        for _ in range(channels)
    ]
    _initialized = True

def process(inputs, outputs, frame_count, sample_rate, params):
    global _initialized
    channels = len(inputs)
    if not _initialized:
        _init(sample_rate, channels)

    drive = params["drive"] / 100.0
    tone = params["tone"]
    chorus_rate = params["chorus_rate"]
    chorus_depth = params["chorus_depth"] / 100.0
    reverb_size = params["reverb_size"] / 100.0
    reverb_damping = params["reverb_damping"] / 100.0
    shimmer = params["shimmer"] / 100.0
    wet_mix = params["mix"]

    # Tone filter coeffs
    tone_coeffs = BiquadCoeffs.lowpass(tone, 0.707, sample_rate)

    # Reverb damping filter coeffs
    damp_freq = 2000 + (1.0 - reverb_damping) * 14000
    damp_coeffs = BiquadCoeffs.lowpass(damp_freq, 0.707, sample_rate)

    # Comb filter feedback based on reverb size
    comb_feedback = 0.7 + reverb_size * 0.25  # 0.7 to 0.95

    # Comb delay times in samples (scaled by reverb size)
    comb_ms = [29.7, 37.1, 41.1, 43.7]
    size_scale = 0.6 + reverb_size * 1.4
    comb_delays_samps = [t * 0.001 * sample_rate * size_scale for t in comb_ms]

    allpass_ms = [5.0, 1.7]
    allpass_delays_samps = [int(t * 0.001 * sample_rate) for t in allpass_ms]
    allpass_g = 0.5

    drive_gain = db_to_gain(drive * 30)

    for ch in range(channels):
        _tone_filters[ch].set_coeffs(tone_coeffs)
        for v in range(2):
            rate = chorus_rate * (1.0 + v * 0.1)
            _chorus_lfos[ch][v].set_freq(rate)
        for c in range(4):
            _reverb_lpfs[ch][c].set_coeffs(damp_coeffs)

        for i in range(frame_count):
            x = inputs[ch][i]

            # === Drive: gain + soft clip ===
            x = soft_clip(x * drive_gain, 1.0 + drive * 2.0)

            # === Tone filter ===
            x = _tone_filters[ch].process_sample(x)

            dry = x

            # === Chorus ===
            chorus_out = 0.0
            base_delay_ms = 7.0
            depth_ms = chorus_depth * 5.0
            for v in range(2):
                mod = _chorus_lfos[ch][v].tick()
                delay_samps = (base_delay_ms + mod * depth_ms) * 0.001 * sample_rate
                delay_samps = max(1.0, delay_samps)
                _chorus_delays[ch][v].write(x)
                chorus_out += _chorus_delays[ch][v].read(delay_samps)
            x = x * 0.5 + chorus_out * (0.3 + shimmer * 0.3)

            # === Reverb (Schroeder-style) ===
            comb_sum = 0.0
            for c in range(4):
                tap = _reverb_delays[ch][c].read(comb_delays_samps[c])
                filtered = _reverb_lpfs[ch][c].process_sample(tap)
                _reverb_delays[ch][c].write(x + filtered * comb_feedback)
                comb_sum += tap
            comb_sum *= 0.25

            # Allpass diffusers
            ap = comb_sum
            for a in range(2):
                tap = _allpass_delays[ch][a].tap(allpass_delays_samps[a])
                _allpass_delays[ch][a].write(ap + tap * allpass_g)
                ap = tap - ap * allpass_g

            reverb_out = ap

            # === Mix ===
            outputs[ch][i] = dry * (1.0 - wet_mix) + reverb_out * wet_mix
