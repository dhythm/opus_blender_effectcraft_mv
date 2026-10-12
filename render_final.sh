#!/bin/zsh
# EffectCraft の Main を 5 並列で PNG 連番に書き出し → ffmpeg で H.264 + 音声に結合する
# 使い方: ./render_final.sh            （全編）
#        ./render_final.sh 16 24      （区間だけ再書き出し）
set -eu
cd "$(dirname "$0")"
EC=${EFFECTCRAFT_CLI:-$HOME/mcp-servers/craft-apps/effectcraft-cli-0.4.0-macos-universal/effectcraft-cli}
OUT="$PWD/renders/final_png"  # EffectCraft は相対パスを .ecproj 基準で解決するので絶対パスにする
mkdir -p "$OUT"

# 素材がすべて揃っているか確認（不足のままビルドするとプレースホルダー/途中までの連番になる）
for pair in s2:180 s3:180 s5:240 s6:240; do
  d=${pair%%:*}; n=${pair##*:}
  c=$(ls renders/$d/f_*.png 2>/dev/null | wc -l | tr -d ' ')
  if [[ $c -ne $n ]]; then echo "renders/$d has $c frames (expected $n)" >&2; exit 1; fi
done

echo "=== build project"
"$EC" script "$PWD/ec/build_main.jsx" --empty --save-as ec/main.ecproj | tail -1

S=${1:-0}
E=${2:-41.5}
N=5
pids=()
for i in $(seq 0 $((N - 1))); do
  a=$(python3 -c "print(round($S + ($E - $S) * $i / $N, 4))")
  b=$(python3 -c "print(round(min($E, $S + ($E - $S) * ($i + 1) / $N + 0.05), 4))")
  "$EC" render --comp Main --out "$OUT/f_[#####].png" --format png --start "$a" --end "$b" --quality best \
    --project ec/main.ecproj > "renders/chunk_$i.log" 2>&1 &
  pids+=($!)
done
fail=0
for p in $pids; do wait $p || fail=1; done
if [[ $fail -ne 0 ]]; then
  echo "chunk render failed; see renders/chunk_*.log" >&2
  exit 1
fi

echo "=== encode"
COUNT=$(ls "$OUT" | wc -l | tr -d ' ')
echo "frames: $COUNT"
missing=$(python3 -c "import os; print([i for i in range(1245) if not os.path.exists('$OUT/f_%05d.png' % i)][:10])")
if [[ "$missing" != "[]" ]]; then echo "missing frames: $missing" >&2; exit 1; fi
ffmpeg -loglevel error -y -framerate 30 -start_number 0 -i "$OUT/f_%05d.png" -i audio/score.wav \
  -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -af "volume=-1.5dB" -c:a aac -b:a 320k -shortest ONE_PROMPT.mp4
ls -la ONE_PROMPT.mp4
