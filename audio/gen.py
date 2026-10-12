"""BGM + SE を numpy で合成する（120BPM, A minor）。timeline.json と同じ時刻表で全イベントを鳴らす。

実行: uv run --with numpy --with scipy python audio/gen.py
出力: audio/score.wav (48kHz / stereo / float32)
"""
import json
import os

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt, sosfilt_zi

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, "..", "timeline.json")))
SR = 48000
DUR = TL["duration"]
N = int(DUR * SR)
BEAT = 60.0 / TL["bpm"]
EV = TL["events"]
rng = np.random.default_rng(7)


def bus():
    return np.zeros((N, 2), dtype=np.float64)


def note(name):
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octv = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + (octv - 4) * 12) / 12)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 * 0.95), "low", fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, min(hi, SR / 2 * 0.95)], "band", fs=SR, output="sos"), x, axis=0)


def swept(x, centers, seg, kind="band", width=(0.7, 1.3)):
    """区間ごとにカットオフを変えるフィルター。区間をまたいでフィルター状態(zi)を引き継ぎ、境目のノイズを防ぐ"""
    y = np.zeros(len(x))
    zi = None
    for i in range(0, len(x), seg):
        c = centers[i]
        if kind == "band":
            sos = butter(2, [c * width[0], min(c * width[1], SR / 2 * 0.95)], "band", fs=SR, output="sos")
        else:
            sos = butter(2, min(c, SR / 2 * 0.95), "low", fs=SR, output="sos")
        if zi is None or zi.shape != sosfilt_zi(sos).shape:
            zi = sosfilt_zi(sos) * 0.0
        y[i:i + seg], zi = sosfilt(sos, x[i:i + seg], zi=zi)
    return y


def place(b, sig, t, gain=1.0, pan=0.0):
    """mono/stereo 信号 sig を時刻 t に加算。pan: -1(L)..1(R)"""
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0:
        return
    if sig.ndim == 1:
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * lg, sig * rg], axis=1) * np.sqrt(2)
    s0 = max(0, -i)
    i0 = max(0, i)
    n = min(len(sig) - s0, N - i0)
    b[i0:i0 + n] += sig[s0:s0 + n] * gain


def tt(d):
    return np.arange(int(d * SR)) / SR


def saw(f, t, phase=0.0):
    p = (f * t + phase) % 1.0
    return 2 * p - 1


def reverb_ir(dur=2.8, decay=3.0, bright=6000):
    t = tt(dur)
    ir = rng.standard_normal((len(t), 2)) * np.exp(-decay * t)[:, None]
    ir = lp(ir, bright)
    ir[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt(np.sum(ir ** 2))


def reverb(x, ir, mix=0.3):
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], axis=1)
    return x * (1 - mix) + wet * mix


# ---------- 音源 ----------

def kick(d=0.55, f0=160, f1=42, punch=1.0):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 6.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.25 * punch
    return np.tanh((body + click) * 1.6)


def snare(d=0.3):
    t = tt(d)
    n = bp(rng.standard_normal(len(t)), 900, 7500) * np.exp(-t * 17)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.6
    return np.tanh((n * 1.4 + tone) * 1.2)


def hat(d=0.05, open_=False):
    t = tt(0.25 if open_ else d)
    return hp(rng.standard_normal(len(t)), 7500) * np.exp(-t * (12 if open_ else 90)) * 0.5


def impact(d=3.5, sub=48):
    t = tt(d)
    f = 28 + (sub - 28) * np.exp(-t * 2.5) + 80 * np.exp(-t * 40)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.3)
    n = lp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 4.5) * 0.8
    crack = hp(rng.standard_normal(len(t)), 2000) * np.exp(-t * 25) * 0.6
    return np.tanh((s * 1.3 + n + crack) * 1.4)


def riser(d, lo=300, hi=9000):
    t = tt(d)
    x = t / d
    n = rng.standard_normal(len(t))
    out = swept(n, lo * (hi / lo) ** x, int(0.01 * SR))
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * x ** 2) / SR) * 0.25
    return (out * 1.5 + tone) * x ** 2.2


def whoosh(d=0.45):
    t = tt(d)
    x = t / d
    env = np.sin(np.pi * x) ** 2
    n = rng.standard_normal(len(t))
    out = swept(n, 400 + 5000 * np.sin(np.pi * x), int(0.005 * SR), width=(0.6, 1.4))
    m = out * env * 2.0
    pan = np.linspace(-1, 1, len(t))
    return np.stack([m * np.cos((pan + 1) * np.pi / 4), m * np.sin((pan + 1) * np.pi / 4)], axis=1) * 1.4


def click(f=2200):
    t = tt(0.03)
    return (rng.standard_normal(len(t)) * np.exp(-t * 600) * 0.6 + np.sin(2 * np.pi * f * t) * np.exp(-t * 250)) * 0.5


def glitch(d=0.12):
    t = tt(d)
    f = rng.choice([220, 440, 880, 1760, 3520])
    sq = np.sign(np.sin(2 * np.pi * f * t * (1 + 3 * (t / d))))
    crush = np.round(rng.standard_normal(len(t)) * 3) / 3 * 0.5
    gate = (np.floor(t * 90) % 2).astype(float)
    return (sq * 0.4 + crush) * gate * np.exp(-t * 6) * 0.6


def supersaw(freqs, d, cutoff=1800, attack=0.4, release=0.8, voices=5, detune=0.012):
    t = tt(d)
    out = np.zeros(len(t))
    for f in freqs:
        for v in range(voices):
            dt = 1 + detune * (v - (voices - 1) / 2) / ((voices - 1) / 2)
            out += saw(f * dt, t, rng.random())
    out /= len(freqs) * voices
    env = np.minimum(1, t / attack) * np.minimum(1, (d - t) / release).clip(0)
    return lp(out * env, cutoff)


def stab(freqs, d=0.45):
    t = tt(d)
    out = sum(saw(f, t) + saw(f * 1.006, t) for f in freqs) / (2 * len(freqs))
    cut_env = 300 + 6000 * np.exp(-t * 14)
    y = swept(out, cut_env, 128, kind="low")  # フィルターエンベロープ
    return y * np.exp(-t * 5)


def pluck(f, d=0.35):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 9)


def bass_note(f, d):
    t = tt(d)
    y = lp(saw(f, t) * 0.7 + np.sin(2 * np.pi * f / 2 * t) * 0.6, 700)
    return y * np.minimum(1, t / 0.005) * np.exp(-t * 3)


# ---------- アレンジ ----------
drums, bassb, music, fx = bus(), bus(), bus(), bus()
CHORDS = [["A2", "C3", "E3", "B3"], ["F2", "A2", "C3", "E3"], ["C3", "E3", "G3", "D4"], ["G2", "B2", "D3", "A3"]]
ROOTS = ["A1", "F1", "C2", "G1"]
kick_times = []


def chord_at(t):
    return int((t // (BEAT * 4)) % 4)


def beats(t0, t1, step=BEAT):
    return list(np.arange(t0, t1 - 1e-6, step))


slow0, slow1 = EV["slowmo"]
fr0, fr1 = EV["freeze"]

# ドラム
for b in beats(3.0, 4.0):  # J カット: S2 の鼓動が S1 の終わりに先行して鳴る
    place(drums, lp(kick(), 300), b, 0.5)
for b in beats(4.0, 10.0):
    place(drums, lp(kick(), 600 + (b - 4) * 400), b, 0.9)
    kick_times.append(b)
for b in beats(6.0, 10.0, BEAT / 2):
    place(drums, hat(), b + BEAT / 2 * 0.0, 0.25 if (b * 4) % 2 else 0.4, pan=0.3)
for b in beats(10.0, 24.0):
    if slow0 - 0.05 <= b < slow1 + 0.2 or 15.5 <= b < 16.0:
        continue
    place(drums, kick(), b, 1.0)
    kick_times.append(b)
for b in beats(10.5, 24.0, BEAT * 2):
    if slow0 <= b < slow1 + 0.2 or b >= 23.0:
        continue
    place(drums, snare(), b, 0.7)
for b in beats(10.0, 24.0, BEAT / 4):
    if slow0 <= b < slow1 + 0.2 or b >= 23.0:
        continue
    acc = 0.32 if abs((b / (BEAT / 2)) - round(b / (BEAT / 2))) < 1e-6 else 0.16
    place(drums, hat(), b, acc, pan=-0.25)
# スロー区間: 鼓動のような重いキック 2 発
for b in (slow0 + 0.35, slow0 + 1.0):
    place(drums, lp(kick(0.9, 120, 35), 250), b, 1.0)
# ビルド: スネアロール 14.3→16.0（8分→16分→32分）
t = slow1 + 0.2
while t < 16.0 - 1e-6:
    x = (t - slow1) / (16.0 - slow1)
    place(drums, snare(0.15), t, 0.25 + 0.5 * x)
    t += BEAT / 2 if x < 0.35 else (BEAT / 4 if x < 0.7 else BEAT / 8)
# S5
for b in beats(24.0, 31.0):
    if fr0 - 0.45 <= b < fr1:
        continue
    place(drums, kick(0.5, 140, 45, 0.6), b, 0.8)
    kick_times.append(b)
for b in beats(24.25, 31.0, BEAT / 2):
    if fr0 - 0.45 <= b < fr1:
        continue
    place(drums, hat(0.08), b, 0.2, pan=0.4)

# ベース
for b in beats(4.0, 10.0):
    place(bassb, bass_note(note(ROOTS[chord_at(b)]), 0.45), b, 0.55)
for b in beats(10.0, 24.0, BEAT / 4):
    if slow0 <= b < slow1 + 0.2 or b >= 23.0:
        continue
    r = note(ROOTS[chord_at(b)])
    step = int(round(b / (BEAT / 4))) % 4
    place(bassb, bass_note(r * (2 if step == 2 else 1), 0.12), b, 0.45)
for b in beats(24.0, 31.0, BEAT):
    if fr0 - 0.45 <= b < fr1:
        continue
    place(bassb, bass_note(note(ROOTS[chord_at(b)]), 0.4), b, 0.45)

# パッド（コード）
for bar in np.arange(0.0, 34.0, BEAT * 4):
    ch = [note(n) for n in CHORDS[chord_at(bar)]]
    cutoff = 900 if bar < 4 else (2200 if bar < 24 else 1600)
    place(music, supersaw(ch, BEAT * 4 + 0.6, cutoff=cutoff, attack=0.5 if bar < 4 else 0.08), bar, 0.38)
# 終幕のコード（ロゴヒット〜L カットの余韻）
final = [note(n) for n in ["A2", "E3", "B3", "C4", "E4", "G4"]]
place(music, supersaw(final, DUR - EV["logo_hit"], cutoff=2600, attack=0.02, release=5.0, voices=7), EV["logo_hit"], 0.55)
for i, n in enumerate(["E5", "A5", "B5", "E6"]):
    t_ = tt(5.0)
    bell = np.sin(2 * np.pi * note(n) * t_) * np.exp(-t_ * 0.9) * 0.25
    place(music, bell, EV["logo_hit"] + i * BEAT / 2, 0.5, pan=(-0.5 + i / 3))
# S4: タイポのヒットにコードスタブ
for i, h in enumerate(EV["typo_hits"]):
    ch = [note(n) * 2 for n in CHORDS[chord_at(h)]]
    place(music, stab(ch), h, 0.55, pan=(-0.3 if i % 2 else 0.3))
# S5: プラックのアルペジオ
arp = ["A4", "C5", "E5", "B5", "E5", "C5"]
for i, b in enumerate(beats(24.0, 31.0, BEAT / 2)):
    if fr0 - 0.45 <= b < fr1:
        continue
    place(music, pluck(note(arp[i % len(arp)])), b, 0.3, pan=np.sin(i) * 0.6)

# ---------- 効果音 ----------
# ドローン
t_ = tt(4.2)
drone = (np.sin(2 * np.pi * 55 * t_) + 0.4 * np.sin(2 * np.pi * 110.3 * t_)) * np.minimum(1, t_ / 1.5)
place(fx, drone, 0.0, 0.25)
# タイピング音
for ln in TL["typing"].values():
    for k in range(len(ln["text"])):
        place(fx, click(1800 + rng.integers(0, 900)), ln["start"] + k / ln["cps"] + rng.normal(0, 0.006), 0.35,
              pan=rng.uniform(-0.2, 0.2))
for g_ in EV["glitch"]:
    place(fx, glitch(0.14), g_, 0.6, pan=rng.uniform(-0.6, 0.6))
place(fx, riser(1.6), 4.0 - 1.6, 0.5)
place(fx, impact(), EV["impact_s2"], 1.0)
place(fx, riser(2.0, 500, 8000), EV["whip"] - 2.0, 0.35)
place(fx, whoosh(0.5), EV["whip"] - 0.25, 0.9)
# スロー区間: 低い持続音のウォッシュ
t_ = tt(slow1 - slow0 + 0.5)
wash = lp(rng.standard_normal(len(t_)), 300) * np.sin(np.pi * t_ / t_[-1]) * 1.2
place(fx, wash, slow0, 0.6)
place(fx, riser(16.0 - slow1, 300, 10000), slow1, 0.6)
place(fx, impact(3.0, 55), EV["impact_s4"], 1.0)
# モンタージュ: 1 フレームごとのティック（ピッチ上昇）
m0, m1 = EV["montage"]
for k, tk in enumerate(np.arange(m0, m1, 1 / 24)):
    place(fx, click(1200 + k * 120), tk, 0.45, pan=((k % 2) * 2 - 1) * 0.5)
place(fx, riser(1.0, 800, 12000), m0, 0.5)
# フリーズ: 直前にテープストップ → 0.5 秒の静寂（高い残響音のみ）→ インパクトで再開
place(fx, impact(2.0, 60), fr1, 0.8)
t_ = tt(fr1 - fr0)
ring = np.sin(2 * np.pi * 2637 * t_) * np.exp(-t_ * 3) * 0.15
place(fx, ring, fr0, 1.0)
place(fx, click(4000), fr0, 1.0)
# 爆発
place(fx, impact(4.0, 40), EV["explode"], 1.1)
for k in range(260):  # 破片が散らばるクラックル
    tk = EV["explode"] + rng.exponential(0.5)
    place(fx, click(3000 + rng.integers(0, 4000)) * 0.4, tk, rng.uniform(0.1, 0.5), pan=rng.uniform(-1, 1))
# 集合: きらめき（加速するアルペジオ）＋リバーススウェル
sh = ["A6", "E6", "B6", "C7", "E7"]
t = 32.0
k = 0
while t < EV["logo_hit"] - 0.02:
    x = (t - 32.0) / (EV["logo_hit"] - 32.0)
    place(fx, pluck(note(sh[k % 5]), 0.25), t, 0.12 + 0.2 * x, pan=rng.uniform(-0.8, 0.8))
    t += 0.12 * (1 - 0.8 * x)
    k += 1
place(fx, riser(2.0, 400, 12000), EV["logo_hit"] - 2.0, 0.6)
place(fx, impact(5.0, 45), EV["logo_hit"], 1.2)

# ---------- ミックス ----------
# サイドチェイン（キックでパッド/ベースをダッキング）
duck = np.ones(N)
dl = int(0.28 * SR)
shape = 1 - 0.6 * np.exp(-np.arange(dl) / (0.06 * SR))
for kt in kick_times:
    i = int(kt * SR)
    n = min(dl, N - i)
    if n > 0:
        duck[i:i + n] = np.minimum(duck[i:i + n], shape[:n])
music *= duck[:, None]
bassb *= duck[:, None]

# スロー区間: 音楽バスを強いローパス＋深いリバーブ
i0, i1 = int(slow0 * SR), int((slow1 + 0.2) * SR)
music[i0:i1] = lp(music[i0:i1], 350)
bassb[i0:i1] *= 0.3

# テープストップ（フリーズ直前 0.45 秒）＋静寂
def tape_stop(b, t0, t1):
    i0, i1 = int(t0 * SR), int(t1 * SR)
    n = i1 - i0
    rate = np.linspace(1.0, 0.0, n) ** 1.5
    pos = i0 + np.cumsum(rate)
    for c in range(2):
        b[i0:i1, c] = np.interp(pos, np.arange(N), b[:, c]) * np.linspace(1, 0.2, n)
    b[i1:int(fr1 * SR)] = 0


for b_ in (drums, bassb, music):
    tape_stop(b_, fr0 - 0.45, fr0)

ir_room = reverb_ir(1.6, 4.0, 7000)
ir_hall = reverb_ir(4.5, 1.3, 5000)
drums = reverb(drums, ir_room, 0.12)
music = reverb(music, ir_hall, 0.35)
fx = reverb(fx, ir_hall, 0.25)
music[i0:i1] = reverb(music[i0:i1], ir_hall, 0.6)

mix = drums * 0.9 + bassb * 0.9 + music * 0.8 + fx * 0.9
mix = hp(mix, 25)
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
# フェード（L カット: 映像が暗転しても 1.5 秒余韻を残す）
fo = int(3.0 * SR)
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
mix *= 0.89 / np.max(np.abs(mix))
wavfile.write(os.path.join(HERE, "score.wav"), SR, mix.astype(np.float32))
print("wrote score.wav", mix.shape, "peak", np.max(np.abs(mix)))
