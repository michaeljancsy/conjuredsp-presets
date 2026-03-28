use conjuredsp::*;
setup!();

params! {
    DRIVE = pct(),
    TONE = pct(),
    BASS = db(),
    MIDS = db(),
    PRESENCE = db(),
    TIGHT = pct(),
    OUTPUT = db(),
}

struct Channel {
    hp: Biquad,
    pre_mid: Biquad,
    inter_scoop: Biquad,
    inter_lp: Biquad,
    eq_bass: Biquad,
    eq_mids: Biquad,
    eq_pres: Biquad,
    cab_hp: Biquad,
    cab_scoop: Biquad,
    cab_peak: Biquad,
    cab_lp: Biquad,
    gate_env: f64,
    sm_drive: f64,
}

impl Channel {
    const fn new() -> Self {
        Self {
            hp: Biquad::new(),
            pre_mid: Biquad::new(),
            inter_scoop: Biquad::new(),
            inter_lp: Biquad::new(),
            eq_bass: Biquad::new(),
            eq_mids: Biquad::new(),
            eq_pres: Biquad::new(),
            cab_hp: Biquad::new(),
            cab_scoop: Biquad::new(),
            cab_peak: Biquad::new(),
            cab_lp: Biquad::new(),
            gate_env: 0.0,
            sm_drive: 20.0,
        }
    }
}

static mut CHS: [Channel; 2] = [Channel::new(), Channel::new()];
static mut INITED: bool = false;
static mut LAST_SR: f32 = 0.0;

unsafe fn init(sr: f64) {
    INITED = true;
    LAST_SR = sr as f32;
    for c in CHS.iter_mut() {
        c.hp.set_coeffs(BiquadCoeffs::highpass(100.0, 0.707, sr));
        c.pre_mid.set_coeffs(BiquadCoeffs::peak(900.0, 1.5, 6.0, sr));
        c.inter_scoop.set_coeffs(BiquadCoeffs::peak(450.0, 0.7, -2.0, sr));
        c.inter_lp.set_coeffs(BiquadCoeffs::lowpass(6000.0, 0.707, sr));
        c.eq_bass.set_coeffs(BiquadCoeffs::lowshelf(200.0, 0.707, 0.0, sr));
        c.eq_mids.set_coeffs(BiquadCoeffs::peak(1000.0, 1.5, 3.0, sr));
        c.eq_pres.set_coeffs(BiquadCoeffs::peak(3200.0, 1.8, 2.0, sr));
        c.cab_hp.set_coeffs(BiquadCoeffs::highpass(75.0, 0.707, sr));
        c.cab_scoop.set_coeffs(BiquadCoeffs::peak(400.0, 0.8, -1.5, sr));
        c.cab_peak.set_coeffs(BiquadCoeffs::peak(2500.0, 2.0, 3.0, sr));
        c.cab_lp.set_coeffs(BiquadCoeffs::lowpass(5500.0, 0.6, sr));
        c.gate_env = 0.0;
        c.sm_drive = 20.0;
    }
}

fn tanhf(x: f64) -> f64 {
    let e2x = (2.0 * x).exp();
    (e2x - 1.0) / (e2x + 1.0)
}

#[no_mangle]
pub extern "C" fn process(
    input: *const f32, output: *mut f32,
    channels: i32, frame_count: i32, sample_rate: f32,
) {
    let ctx = ctx(input, output, channels, frame_count, sample_rate);
    unsafe {
        let sr = sample_rate as f64;
        if !INITED || LAST_SR != sample_rate {
            init(sr);
        }

        let dp = ctx.param(DRIVE) as f64 / 100.0;
        let tp = ctx.param(TONE) as f64 / 100.0;
        let out_g = db_to_gain(ctx.param(OUTPUT) as f64);
        let drive = 4.0 + dp.powf(1.5) * 46.0;
        let hp_f = 60.0 + (ctx.param(TIGHT) as f64 / 100.0) * 140.0;
        let cab_lp_f = 3500.0 + tp * 4000.0;
        let gate_th: f64 = 0.005;
        let gate_att = smooth_coeff(0.1, sr);
        let gate_rel = smooth_coeff(80.0, sr);
        let p_sm = smooth_coeff(5.0, sr);

        let n_ch = ctx.channels().min(2);
        for ch in 0..n_ch {
            let c = &mut CHS[ch];

            c.hp.set_coeffs(BiquadCoeffs::highpass(hp_f, 0.707, sr));
            c.eq_bass.set_coeffs(BiquadCoeffs::lowshelf(200.0, 0.707, ctx.param(BASS) as f64, sr));
            c.eq_mids.set_coeffs(BiquadCoeffs::peak(1000.0, 1.5, ctx.param(MIDS) as f64 + 3.0, sr));
            c.eq_pres.set_coeffs(BiquadCoeffs::peak(3200.0, 1.8, ctx.param(PRESENCE) as f64 + 2.0, sr));
            c.cab_lp.set_coeffs(BiquadCoeffs::lowpass(cab_lp_f, 0.6, sr));

            let mut gate_env = c.gate_env;
            let mut sm_d = c.sm_drive;

            for i in 0..ctx.frames() {
                let mut x = ctx.input(ch, i) as f64;

                // Noise gate
                let ae = x.abs();
                if ae > gate_env {
                    gate_env = gate_att * gate_env + (1.0 - gate_att) * ae;
                } else {
                    gate_env = gate_rel * gate_env + (1.0 - gate_rel) * ae;
                }
                if gate_env < gate_th {
                    let r = gate_env / gate_th;
                    x *= r * r;
                }

                // Smooth drive
                sm_d = p_sm * sm_d + (1.0 - p_sm) * drive;

                // Input HP (tightness)
                x = c.hp.process_sample(x);

                // Pre-emphasis: mid bark
                x = c.pre_mid.process_sample(x);

                // Stage 1: initial breakup
                x = tanhf(x * sm_d * 0.175);

                // Inter-stage shaping
                x = c.inter_scoop.process_sample(x);

                // Stage 2: main crunch
                x = tanhf(x * sm_d * 0.12);

                // Inter-stage HF taming
                x = c.inter_lp.process_sample(x);

                // Stage 3: asymmetric saturation
                let x2 = x * 2.0;
                if x2 > 0.0 {
                    x = tanhf(x2 * 1.15);
                } else {
                    x = tanhf(x2 * 0.85);
                }

                // Tone stack
                x = c.eq_bass.process_sample(x);
                x = c.eq_mids.process_sample(x);
                x = c.eq_pres.process_sample(x);

                // Cabinet sim
                x = c.cab_hp.process_sample(x);
                x = c.cab_scoop.process_sample(x);
                x = c.cab_peak.process_sample(x);
                x = c.cab_lp.process_sample(x);

                ctx.set_output(ch, i, (x * out_g) as f32);
            }

            c.gate_env = gate_env;
            c.sm_drive = sm_d;
        }
    }
}
