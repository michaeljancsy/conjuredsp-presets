use conjuredsp::*;
setup!();
// nam!("tone3000://60092/351559");
conjuredsp::nam!("tone3000://28135/110358");


params! {
    INPUT_GAIN = db().min(-20.0).max(20.0).default(0.0),
    OUTPUT_LEVEL = db().min(-20.0).max(6.0).default(0.0),
    MIX = mix().default(1.0),
}

#[no_mangle]
pub extern "C" fn process(
    input: *const f32, output: *mut f32,
    channels: i32, frame_count: i32, sample_rate: f32,
) {
    let ctx = ctx(input, output, channels, frame_count, sample_rate);
    unsafe {
        let input_gain = db_to_gain(ctx.param(INPUT_GAIN) as f64) as f32;
        let output_gain = db_to_gain(ctx.param(OUTPUT_LEVEL) as f64) as f32;
        let mix_val = ctx.param(MIX) as f32;

        if let Some(model) = NAM_MODEL.as_mut() {
            for c in 0..ctx.channels() {
                let n = ctx.frames();
                for i in 0..n {
                    NAM_IN[i] = ctx.input(c, i) * input_gain;
                }
                model.process_buffer(&NAM_IN[..n], &mut NAM_OUT[..n], c);
                for i in 0..n {
                    let dry = ctx.input(c, i);
                    let wet = NAM_OUT[i] * output_gain;
                    ctx.set_output(c, i, dry * (1.0 - mix_val) + wet * mix_val);
                }
            }
        }
    }
}
