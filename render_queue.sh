#!/bin/zsh
# 使い方: ./render_queue.sh shot_s2_field.py [shot_s3_tunnel.py ...]  — 順番に本番レンダリング
cd "$(dirname "$0")"
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for s in "$@"; do
  echo "=== $s start $(date +%T)"
  "$BLENDER" -b --factory-startup -P blender/$s 2>&1 | grep -E "Error|Traceback|Saved: .*f_0*(1|30|60|90|120|150|180|210|240)\.png" || true
  echo "=== $s done $(date +%T)"
done
