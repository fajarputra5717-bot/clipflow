#!/usr/bin/env bash
# Rebuild worker/assets/emoji/*.png from Google Noto Emoji SVGs (Apache 2.0, see worker/assets/LICENSES.md).
# 256 px RGBA, rendered with the UI tests' Playwright Chromium. Names = codepoints in shared/edit_director.EMOJI.
set -euo pipefail
TAG=v2026-09-24-unicode18_0
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
CODES=$(cd "$ROOT" && python3 -c "from shared.edit_director import EMOJI; print(' '.join(EMOJI.values()))")
for c in $CODES; do
  curl -sfL -o "$TMP/$c.svg" "https://raw.githubusercontent.com/googlefonts/noto-emoji/$TAG/2D/svg/emoji_u$c.svg"
done
cat > "$ROOT/tests/ui/.make_emoji.js" <<'JS'
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const [dir, out] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 256, height: 256 } });
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.svg'))) {
    const b64 = fs.readFileSync(path.join(dir, f)).toString('base64');
    await p.setContent(`<body style="margin:0"><img style="width:256px;height:256px;display:block" src="data:image/svg+xml;base64,${b64}">`);
    await p.screenshot({ path: path.join(out, f.replace('.svg', '.png')), omitBackground: true });
  }
  await b.close();
})();
JS
trap 'rm -rf "$TMP" "$ROOT/tests/ui/.make_emoji.js"' EXIT
(cd "$ROOT/tests/ui" && node .make_emoji.js "$TMP" "$ROOT/worker/assets/emoji")
ls "$ROOT/worker/assets/emoji"
