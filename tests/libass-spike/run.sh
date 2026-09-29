#!/bin/sh
# Re-run the 065 libass spike in a throwaway worker container (no network):
#   docker run --rm --network none \
#     -v "$PWD/worker/fonts:/usr/share/fonts/truetype/clipflow:ro" \
#     -v "$PWD/tests/libass-spike:/w:ro" -v /tmp/spike-out:/out \
#     --entrypoint sh riftstorm-worker /w/run.sh
# Frames land in /tmp/spike-out; fontselect lines (which file/instance libass picked) in *.log.
set -e
fc-cache -f >/dev/null
for t in 0.07 0.37 0.67 1.00; do
  ffmpeg -hide_banner -loglevel error -f lavfi -i color=c=0x404040:s=1080x1920:d=3 -ss $t \
    -vf "ass=/w/r18.ass" -frames:v 1 -y /out/r18_$t.png
done
for f in fonts fonts2; do
  ffmpeg -hide_banner -loglevel verbose -f lavfi -i color=c=0x404040:s=1080x1920:d=1 \
    -vf "ass=/w/$f.ass" -frames:v 1 -y /out/$f.png 2>&1 | grep fontselect > /out/$f.log || true
done
