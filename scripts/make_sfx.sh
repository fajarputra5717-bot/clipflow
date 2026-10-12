#!/bin/sh
# Auto Edit E3: generate the bundled SFX with ffmpeg (original works, released CC0; see worker/assets/LICENSES.md).
# Run in a throwaway worker container:  docker run --rm -v "$PWD/worker/assets/sfx:/out" -v "$PWD/scripts:/s:ro" \
#   --entrypoint sh riftstorm-worker:latest /s/make_sfx.sh
# 48 kHz mono WAV, peak-normalised to -3 dBFS by the final volume/alimiter step.
set -e
O=${OUT:-/out}
gen() { name=$1; dur=$2; expr=$3; post=$4
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "aevalsrc=$expr:s=48000:d=$dur" \
    -af "${post}afade=t=out:st=$(awk "BEGIN{print $dur - 0.05}"):d=0.05,alimiter=limit=0.708:level=0,aformat=sample_rates=48000:channel_layouts=mono" \
    -c:a pcm_s16le "$O/$name.wav"; }
# whoosh: band-passed noise swelling in and out
gen whoosh 0.55 "(random(0)-0.5)*sin(PI*t/0.55)^2" "highpass=f=400,lowpass=f=5000,bandpass=f=1800:width_type=o:w=2.5,volume=8,"
# boom: falling low sine + a short noise thump, long decay
gen boom 1.4 "0.9*sin(2*PI*(38+30*exp(-6*t))*t)*exp(-2.6*t)+0.35*(random(1)-0.5)*exp(-25*t)" "lowpass=f=900,"
# bass hit: fast pitch-drop kick
gen bass_hit 0.6 "sin(2*PI*(45*t+(140/9)*(1-exp(-9*t))))*exp(-5.5*t)" "lowpass=f=600,"
# ding: bell partials
gen ding 1.2 "0.6*sin(2*PI*1318*t)*exp(-3.5*t)+0.25*sin(2*PI*2637*t)*exp(-6*t)+0.12*sin(2*PI*3951*t)*exp(-9*t)" ""
# record scratch: noisy tone with a fast pitch wobble
gen record_scratch 0.6 "0.7*sin(2*PI*(500*t+60*sin(2*PI*7*t)))*(random(2)-0.5)*2*exp(-2*t)" "bandpass=f=1200:width_type=o:w=3,volume=4,"
ls -la "$O"
