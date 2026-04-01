"""
Here's what
  the preset does:                
                           
  - Left channel — Marshall JCM800
   2203 Modified ("Bad Boys"
  blend, SM57 mic): classic       
  British crunch, warm midrange,  
  natural sag                     
  - Right channel — ENGL SE E670: 
  tight, aggressive high-gain,    
  more modern and clinical
                                  
  Both amps get the same input    
  (channel 0), so a mono guitar
  comes out wide in stereo with   
  two distinct amp characters.
  Classic "double-track" feel
  without actually doubling.

  Parameters:
  - input_gain — drive into the
  amp models (push for more       
  saturation)              
  - output_gain — trim the output 
  level                          
  - mix — blend dry/wet (keep at  
  1.0 for full amp sound)
  """


import numpy as np
from conjuredsp.nam import load_model
from conjuredsp import db, mix

PARAMS = {
    "input_gain": db(default=0),
    "output_gain": db(default=0),
    "mix": mix(default=1.0),
}

# Left: Marshall JCM800 2203 Modified — classic British rock crunch
# Right: ENGL SE E670 — tight, modern high-gain
_model_left = load_model("tone3000://44209/233039")
_model_right = load_model("tone3000://34/82524")

def process(inputs, outputs, frame_count, sample_rate, params):
    in_gain = 10 ** (params["input_gain"] / 20.0)
    out_gain = 10 ** (params["output_gain"] / 20.0)
    mix_val = params["mix"]

    # Use channel 0 as the source for both sides (mono guitar → dual amp)
    dry = inputs[0][:frame_count]
    driven = dry * in_gain

    wet_left = _model_left.process(driven, 0) * out_gain
    wet_right = _model_right.process(driven, 0) * out_gain

    outputs[0][:frame_count] = dry * (1 - mix_val) + wet_left * mix_val
    outputs[1][:frame_count] = dry * (1 - mix_val) + wet_right * mix_val
