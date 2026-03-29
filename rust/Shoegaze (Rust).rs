
use conjuredsp::*;
setup!();

params! {
    DRIVE = pct().default(60.0),
    TONE = freq().min(1000.0).max(16000.0).default(4000.0),
    CHORUS_RATE = param(0.1, 5.0).default(1.2).unit("Hz"),
    CHORUS_DEPTH = pct().default(60.0),
    REVERB_SIZE = pct().default(80.0),
    REVERB_DAMPING = pct().default(70.0),
    SHIMMER = pct().default(30.0),
    MIX = mix().default(0.75),
}

static mut TONE_FILTERS: [Biquad; 2] = [Biquad::new(); 2];
static mut CHORUS_DELAYS: [[DelayLine<2205>; 2]; 2] = [[DelayLine::new(); 2]; 2];
static mut CHORUS_LFOS: [[Lfo; 2]; 2] = [[Lfo::new(); 2]; 2];
static mut COMB_DELAYS: [[DelayLine<8820>; 4]; 2] = [[DelayLine::new(); 4]; 2];
static mut COMB_LPFS: [[Biquad; 4]; 2] = [[Biquad::new(); 4]; 2];
static mut AP_DELAYS: [[DelayLine<441>; 2]; 2] = [[DelayLine::new(); 2]; 2];

#[no_mangle]
pub extern "C" fn process(
    input: *const f32, output: *mut f32,
    channels: i32, frame_count: i32, sample_rate: f32,
) {
    let ctx = ctx(input, output, channels, frame_count, sample_rate);
    let sr = sample_rate as f64;

    let drive = ctx.param(DRIVE) as f64 / 100.0;
    let tone = ctx.param(TONE) as f64;
    let chorus_rate = ctx.param(CHORUS_RATE) as f64;
    let chorus_depth = ctx.param(CHORUS_DEPTH) as f64 / 100.0;
    let reverb_size = ctx.param(REVERB_SIZE) as f64 / 100.0;
    let reverb_damping = ctx.param(REVERB_DAMPING) as f64 / 100.0;
    let shimmer = ctx.param(SHIMMER) as f64 / 100.0;
    let wet_mix = ctx.param(MIX) as f64;

    let tone_coeffs = BiquadCoeffs::lowpass(tone, 0.707, sr);
    let damp_freq = 2000.0 + (1.0 - reverb_damping) * 14000.0;
    let damp_coeffs = BiquadCoeffs::lowpass(damp_freq, 0.707, sr);

    let comb_feedback = 0.7 + reverb_size * 0.25;
    let size_scale = 0.6 + reverb_size * 1.4;
    let comb_ms: [f64; 4] = [29.7, 37.1, 41.1, 43.7];
    let comb_delays_samps: [f64; 4] = [
        comb_ms[0] * 0.001 * sr * size_scale,
        comb_ms[1] * 0.001 * sr * size_scale,
        comb_ms[2] * 0.001 * sr * size_scale,
        comb_ms[3] * 0.001 * sr * size_scale,
    ];

    let allpass_samps: [usize; 2] = [
        (5.0 * 0.001 * sr) as usize,
        (1.7 * 0.001 * sr) as usize,
    ];
    let allpass_g: f64 = 0.5;
    let drive_gain = db_to_gain(drive * 30.0);

    unsafe {
        for c in 0..ctx.channels() {
            TONE_FILTERS[c].set_coeffs(tone_coeffs);

            CHORUS_LFOS[c][0].init(sr, chorus_rate);
            CHORUS_LFOS[c][1].init(sr, chorus_rate * 1.1);
            CHORUS_LFOS[c][1].set_waveform(Waveform::Triangle);

            for k in 0..4 {
                COMB_LPFS[c][k].set_coeffs(damp_coeffs);
            }

            for i in 0..ctx.frames() {
                let mut x = ctx.input(c, i) as f64;

                // Drive
                x = soft_clip(x * drive_gain, 1.0 + drive * 2.0);

                // Tone filter
                x = TONE_FILTERS[c].process_sample(x);

                let dry = x;

                // Chorus: 2 voices
                let base_delay_ms = 7.0;
                let depth_ms = chorus_depth * 5.0;
                let mut chorus_out = 0.0;
                for v in 0..2 {
                    let mod_val = if c == 0 {
                        CHORUS_LFOS[c][v].tick()
                    } else {
                        CHORUS_LFOS[c][v].value
                    };
                    let delay_samps = ((base_delay_ms + mod_val * depth_ms) * 0.001 * sr).max(1.0);
                    CHORUS_DELAYS[c][v].write(x as f32);
                    chorus_out += CHORUS_DELAYS[c][v].read(delay_samps) as f64;
                }
                x = x * 0.5 + chorus_out * (0.3 + shimmer * 0.3);

                // Reverb: 4 comb filters
                let mut comb_sum = 0.0;
                for k in 0..4 {
                    let tap = COMB_DELAYS[c][k].read(comb_delays_samps[k]) as f64;
                    let filtered = COMB_LPFS[c][k].process_sample(tap);
                    COMB_DELAYS[c][k].write((x + filtered * comb_feedback) as f32);
                    comb_sum += tap;
                }
                comb_sum *= 0.25;

                // 2 allpass diffusers
                let mut ap = comb_sum;
                for a in 0..2 {
                    let tap = AP_DELAYS[c][a].tap(allpass_samps[a]) as f64;
                    AP_DELAYS[c][a].write((ap + tap * allpass_g) as f32);
                    ap = tap - ap * allpass_g;
                }

                let out = dry * (1.0 - wet_mix) + ap * wet_mix;
                ctx.set_output(c, i, out as f32);
            }
        }
    }
}
