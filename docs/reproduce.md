# 再現手順

## 必要なもの

| ツール | 確認したバージョン | 既定のパス（環境変数で上書き可） |
|---|---|---|
| Blender | 5.2.2 LTS | `/Applications/Blender.app/Contents/MacOS/Blender`（`BLENDER`） |
| EffectCraft CLI | 0.4.0 | `~/mcp-servers/craft-apps/effectcraft-cli-0.4.0-macos-universal/effectcraft-cli`（`EFFECTCRAFT_CLI`） |
| ffmpeg | 7 以降（libx264） | `PATH` 上 |
| uv | — | `PATH` 上（numpy / scipy を一時環境で使う） |

フォントは macOS 標準のもの（ヒラギノ角ゴシック、Helvetica Neue、Avenir Next、Menlo）を使っています。

## 1. 音楽

```bash
uv run --with numpy --with scipy python audio/gen.py
```

`timeline.json` のイベント時刻をもとに `audio/score.wav`（48kHz / ステレオ / 41.5 秒）を生成します。

## 2. Blender ショット

プレビュー（1/3 解像度・低サンプル）で、特定のフレームを確認する場合:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P blender/shot_s2_field.py -- --still 90 --preview
```

出力先は `renders/s2_preview/still_0090.png` です。その他のオプションは次のとおりです。

- `--frames 1:60`：範囲を指定してレンダリングする
- `--step 5`：5 フレームおきにレンダリングする

本番（フル HD、PNG 連番）:

```bash
./render_queue.sh shot_s2_field.py shot_s3_tunnel.py shot_s5_core.py shot_s6_logo.py
```

| ショット | フレーム数 | M5 でのレンダリング時間 |
|---|---|---|
| S2 | 180 | 8m23s |
| S3 | 180 | 5m43s |
| S5 | 240 | 10m34s |
| S6 | 240 | 16m14s |

## 3. 画面に出す数字を計測する（任意）

```bash
for sh in s2:shot_s2_field s3:shot_s3_tunnel s5:shot_s5_core s6:shot_s6_logo; do
  SHOT=${sh%%:*} NO_RENDER=1 /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    -P blender/${sh##*:}.py -P blender/stats.py 2>&1 | grep STAT
done
```

EffectCraft のキーフレーム総数（`ec/build_main.jsx` 先頭の `KEYS` に記入している値）:

```bash
"$EFFECTCRAFT_CLI" script ec/count_keys.jsx ec/main.ecproj
```

## 4. EffectCraft で合成して mp4 にする

```bash
./render_final.sh            # 全編
./render_final.sh 16 24      # 区間だけ書き出し直す（その後のエンコードは全フレームが必要）
```

処理の流れは次のとおりです。

1. 素材のフレーム数を確認する（不足していれば中断）
2. `ec/main.ecproj` を構築する（`ec/build_main.jsx` は絶対パスで渡す）
3. 5 並列で `renders/final_png/f_00000.png` 〜 `f_01244.png` を書き出す
4. 欠番がないか確認する
5. ffmpeg で `ONE_PROMPT.mp4`（H.264 CRF 15 / AAC 320k / bt709）を作る

特定の時刻の 1 フレームだけ確認する場合:

```bash
"$EFFECTCRAFT_CLI" render-frame --comp Main --time 18.2 --out check.png --max-side 960 --project ec/main.ecproj
```

## 5. MCP で操作する場合

Claude Code に次の MCP を登録しておくと、同じエンジンを MCP 経由でも操作できます。

```bash
claude mcp add -s user blender -e BLENDER_MCP_SAFE_MODE=1 -e DISABLE_TELEMETRY=true -- uvx mcp-for-blender
claude mcp add -s user effectcraft -- "$EFFECTCRAFT_CLI" mcp
```

Blender の MCP を使うには、Blender の GUI を起動し、アドオン側のサーバーを開始しておく必要があります。このリポジトリのスクリプトはヘッドレス実行を前提としているため、MCP は不要です。
