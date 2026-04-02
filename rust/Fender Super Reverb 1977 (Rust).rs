
use conjuredsp::*;
setup!();
nam!("tone3000://19/51");

params! {
    INPUT_GAIN = db().default(0.0),
    OUTPUT_LEVEL = db().default(0.0),
    TONE = freq().default(8000.0),
    MIX = mix().default(1.0),
}

static mut FILTERS: [Biquad; 2] = [Biquad::new(); 2];

#[no_mangle]
pub extern "C" fn process(
    input: *const f32, output: *mut f32,
    channels: i32, frame_count: i32, sample_rate: f32,
) {
    let ctx = ctx(input, output, channels, frame_count, sample_rate);
    unsafe {
        let in_gain = db_to_gain(ctx.param(INPUT_GAIN) as f64) as f32;
        let out_gain = db_to_gain(ctx.param(OUTPUT_LEVEL) as f64) as f32;
        let mix_val = ctx.param(MIX);
        let tone = ctx.param(TONE);

        let coeffs = BiquadCoeffs::lowpass(tone as f64, 0.707, sample_rate as f64);

        if let Some(model) = NAM_MODEL.as_mut() {
            let n = ctx.frames();
            for c in 0..ctx.channels() {
                // Feed input with gain into NAM
                for i in 0..n {
                    NAM_IN[i] = ctx.input(c, i) * in_gain;
                }
                model.process_buffer(&NAM_IN[..n], &mut NAM_OUT[..n], c);

                // Apply tone filter and mix
                FILTERS[c].set_coeffs(coeffs);
                for i in 0..n {
                    let wet = FILTERS[c].process_sample(NAM_OUT[i] as f64) as f32;
                    let dry = ctx.input(c, i);
                    ctx.set_output(c, i, (dry * (1.0 - mix_val) + wet * mix_val) * out_gain);
                }
            }
        }
    }
}
