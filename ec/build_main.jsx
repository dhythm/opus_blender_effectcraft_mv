// EffectCraft マスターコンポ構築スクリプト（After Effects 互換 JSX）
// 実行: effectcraft-cli script build_main.jsx --empty --save-as main.ecproj
// Blender のレンダー（renders/s2,s3,s5,s6）と audio/score.wav を読み込み、
// S1 イントロ / S4 キネティックタイポ / HUD / トランジション / グレードを組み立てる。

// リポジトリのルート（このスクリプトの 1 つ上）。どこに clone しても動く
var ROOT = File($.fileName).parent.parent.fsName + "/";
if (ROOT.charAt(0) !== "/" || ROOT === "/") throw new Error("build_main.jsx は絶対パスで実行してください（例: \"$PWD/ec/build_main.jsx\"）: ROOT=" + ROOT);
var W = 1920, H = 1080, FPS = 30, DUR = 41.5;
var CYAN = [0.2, 0.8, 1.0], MAGENTA = [1.0, 0.15, 0.5], ORANGE = [1.0, 0.5, 0.1], WHITE = [1, 1, 1], BLACK = [0, 0, 0];
var MONO = "Menlo-Regular", MONO_B = "Menlo-Bold", SANS_B = "HelveticaNeue-Bold", SANS_M = "HelveticaNeue-Medium",
    SANS_L = "HelveticaNeue-Light", JP = "HiraginoSans-W3", JP_B = "HiraginoSans-W6";
// S3 最終フレームのポータル直径（px）。S4 冒頭の白い円をこれに合わせてマッチカットする
var PORTAL_D = 560;
// コードが生成した EffectCraft のキーフレーム総数（count_keys.jsx で計測して記入）
var KEYS = "672";

// ---------------- ヘルパー ----------------
function imp(path, seq) {
    var io = new ImportOptions(new File(path));
    if (seq) io.sequence = true;
    return app.project.importFile(io);
}
function T(layer, mn) { return layer.property("ADBE Transform Group").property(mn); }
function fxAdd(layer, mn) { return layer.property("ADBE Effect Parade").addProperty(mn); }

// keys: [[t, v], ...] / ease: "linear" | "hold" | "ease" | "out"(急発進→ゆっくり停止) | "in"
function kf(prop, keys, ease) {
    // EffectCraft はキー時刻をフレームに丸める。同じフレームに重なると上書きされるため、
    // 衝突したら手前のキーを 1 フレーム前へずらす（例: 3.99 と 4.0）
    var fr = [];
    for (var i = 0; i < keys.length; i++) fr.push(Math.round(keys[i][0] * FPS));
    for (var j = fr.length - 1; j > 0; j--) if (fr[j - 1] >= fr[j]) fr[j - 1] = fr[j] - 1;
    for (var i2 = 0; i2 < keys.length; i2++) prop.setValueAtTime(fr[i2] / FPS, keys[i2][1]);
    if (!ease) return prop;
    for (var k = 1; k <= prop.numKeys; k++) {
        try {
            if (ease === "hold") { prop.setInterpolationTypeAtKey(k, KeyframeInterpolationType.HOLD); continue; }
            if (ease === "linear") { prop.setInterpolationTypeAtKey(k, KeyframeInterpolationType.LINEAR); continue; }
            var infIn = ease === "out" ? 85 : (ease === "in" ? 15 : 70);
            var infOut = ease === "out" ? 15 : (ease === "in" ? 85 : 70);
            var v = prop.keyValue(k);
            var dims = 1;
            if (v instanceof Array && !(prop.propertyValueType === PropertyValueType.TwoD_SPATIAL ||
                                         prop.propertyValueType === PropertyValueType.ThreeD_SPATIAL)) dims = v.length;
            var ei = [], eo = [];
            for (var d = 0; d < dims; d++) { ei.push(new KeyframeEase(0, infIn)); eo.push(new KeyframeEase(0, infOut)); }
            prop.setTemporalEaseAtKey(k, ei, eo);
        } catch (e) { /* イーズ非対応のプロパティは既定補間のまま */ }
    }
    return prop;
}

function solid(comp, color, name, w, h) {
    return comp.layers.addSolid(color, name, w || W, h || H, 1);
}
function adjustment(comp, name) {
    var l = solid(comp, [1, 1, 1], name);
    l.adjustmentLayer = true;
    return l;
}
function span(layer, t0, t1) { layer.inPoint = t0; layer.outPoint = t1; return layer; }

// テキスト。o: {font,size,color,pos,just,tracking}
function txt(comp, s, o) {
    o = o || {};
    var l = comp.layers.addText(s);
    var sp = l.property("ADBE Text Properties").property("ADBE Text Document");
    var td = sp.value;
    td.font = o.font || SANS_B;
    td.fontSize = o.size || 100;
    td.fillColor = o.color || WHITE;
    td.applyFill = true;
    td.justification = o.just === "left" ? ParagraphJustification.LEFT_JUSTIFY :
        (o.just === "right" ? ParagraphJustification.RIGHT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY);
    if (o.tracking != null) td.tracking = o.tracking;
    sp.setValue(td);
    // pos は「見た目の中心 y」で指定し、ベースラインへ補正する
    var p = o.pos || [W / 2, H / 2];
    T(l, "ADBE Position").setValue([p[0], p[1] + (o.size || 100) * 0.35]);
    if (o.name) l.name = o.name;
    return l;
}

var TA = { opacity: "ADBE Text Opacity", blur: "ADBE Text Blur", scale: "ADBE Text Scale 3D",
           position: "ADBE Text Position 3D", rotation: "ADBE Text Rotation", fill: "ADBE Text Fill Color" };
// 文字単位のアニメーター。mode "in": props の状態から通常へ（左→右に解除）/ "out": 通常から props へ
function charAnim(l, props, t0, t1, o) {
    o = o || {};
    var an = l.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator");
    var ap = an.property("ADBE Text Animator Properties");
    for (var k in props) {
        var p;
        if (k === "tracking") { ap.addProperty("ADBE Text Tracking Amount"); p = ap.property("Tracking Amount"); }
        else p = ap.addProperty(TA[k]);
        p.setValue(props[k]);
    }
    var sel = an.property("ADBE Text Selectors").property(1);
    var adv = sel.property("advanced");
    if (o.smooth != null) adv.property("Smoothness").setValue(o.smooth);
    if (o.random) adv.property("Randomize Order").setValue(1);
    if (o.mode === "out") {
        sel.property("start").setValue(0);
        kf(sel.property("end"), [[t0, 0], [t1, 100]], o.ease || "linear");
    } else {
        kf(sel.property("start"), [[t0, 0], [t1, 100]], o.ease || "linear");
    }
    return an;
}
function typewriter(l, t0, cps, nChars) {
    return charAnim(l, { opacity: 0 }, t0, t0 + nChars / cps, { smooth: 0, ease: "linear" });
}

function shapeLayer(comp, name) { var l = comp.layers.addShape(); l.name = name; return l; }
function shapeGroup(l) {
    var g = l.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    return g.property("ADBE Vectors Group");
}
function ellipse(cont, size) { var e = cont.addProperty("ADBE Vector Shape - Ellipse"); e.property("ADBE Vector Ellipse Size").setValue(size); return e; }
function rect(cont, size, round) {
    var r = cont.addProperty("ADBE Vector Shape - Rect");
    r.property("ADBE Vector Rect Size").setValue(size);
    if (round) r.property("ADBE Vector Rect Roundness").setValue(round);
    return r;
}
function fill(cont, color) { var f = cont.addProperty("ADBE Vector Graphic - Fill"); f.property("ADBE Vector Fill Color").setValue(color); return f; }
function stroke(cont, color, w) {
    var s = cont.addProperty("ADBE Vector Graphic - Stroke");
    s.property("ADBE Vector Stroke Color").setValue(color);
    s.property("ADBE Vector Stroke Width").setValue(w);
    return s;
}
function trim(cont) { return cont.addProperty("ADBE Vector Filter - Trim"); }

// 横線（中央から左右へ描画）
function drawLine(comp, y, width, color, t0, t1, tOut) {
    var l = shapeLayer(comp, "line");
    var c = shapeGroup(l);
    rect(c, [width, 3]);
    fill(c, color);
    T(l, "ADBE Position").setValue([W / 2, y]);
    kf(T(l, "ADBE Scale"), [[t0, [0, 100]], [t1, [100, 100]]], "out");
    if (tOut) kf(T(l, "ADBE Scale"), [[tOut, [100, 100]], [tOut + 0.15, [0, 100]]], "in");
    return l;
}

// ======================================================================
// フッテージ
// ======================================================================
var fS2 = imp(ROOT + "renders/s2/f_0001.png", true);
var fS3 = imp(ROOT + "renders/s3/f_0001.png", true);
// レンダリング途中でも構築できるよう、無ければプレースホルダーにする
function impSeq(path, dur) {
    try { return imp(path, true); }
    catch (e) { writeLn("placeholder: " + path); return app.project.importPlaceholder("missing", W, H, FPS, dur); }
}
var fS5 = impSeq(ROOT + "renders/s5/f_0001.png", 8);
var fS6 = impSeq(ROOT + "renders/s6/f_0001.png", 8);
var fAudio = imp(ROOT + "audio/score.wav", false);

// ======================================================================
// S1: ターミナル（0〜4s）
// ======================================================================
var s1 = app.project.items.addComp("S1_Intro", W, H, 1, 4, FPS);
s1.bgColor = [0.012, 0.016, 0.03];
(function () {
    var bg = solid(s1, [0.012, 0.016, 0.03], "bg");
    // うごめくノイズの背景
    var nz = solid(s1, BLACK, "noise");
    var fn = fxAdd(nz, "ADBE Fractal Noise");
    fn.property("Evolution").expression = "time * 120";
    fn.property("Contrast").setValue(160);
    fn.property("Brightness").setValue(-30);
    var tn = fxAdd(nz, "ADBE Tint");
    tn.property("Map White To").setValue([0.1, 0.3, 0.6]);
    nz.blendingMode = BlendingMode.SCREEN;
    T(nz, "ADBE Opacity").setValue(22);
    // 走査線
    var sl = solid(s1, WHITE, "scan");
    var vb = fxAdd(sl, "ADBE Venetian Blinds");
    vb.property("Transition Completion").setValue(70);
    vb.property("Direction").setValue(90);
    vb.property("Width").setValue(4);
    T(sl, "ADBE Opacity").setValue(4);

    // 実際の依頼文をタイプ → 実際に走らせたコマンドのログ（数字はすべて実測値）
    var REQ = "＞ プロ顔負けの、最強の動画を作ってください。";
    var X0 = 250, JADV = 50, RCPS = 15, RT0 = 0.3;
    txt(s1, "you@studio  ~/opus_motion  %", { font: MONO, size: 24, color: [0.45, 0.5, 0.6], pos: [X0, 350], just: "left" });
    var l1 = txt(s1, REQ, { font: JP_B, size: 50, color: WHITE, pos: [X0, 425], just: "left", name: "request" });
    typewriter(l1, RT0, RCPS, REQ.length);
    var g1 = fxAdd(l1, "ADBE Glo2");
    g1.property("Glow Radius").setValue(25);
    g1.property("Glow Intensity").setValue(0.7);
    var LOG = [
        "[ok] blender      shot_s2_field.py    22,020 pillars     8m23s",
        "[ok] blender      shot_s3_tunnel.py   456 m FPV path     5m43s",
        "[ok] blender      shot_s5_core.py     28,909 shards     10m34s",
        "[ok] blender      shot_s6_logo.py     28,455 voxels     16m14s",
        "[ok] numpy        audio/gen.py        120 BPM score      synth",
        "[ok] effectcraft  build_main.jsx      " + KEYS + " keyframes by code",
        "[>>] render       1,245 frames  ->  ONE_PROMPT.mp4"
    ];
    for (var li = 0; li < LOG.length; li++) {
        var ln = txt(s1, LOG[li], { font: MONO, size: 25, color: li === LOG.length - 1 ? CYAN : [0.62, 0.68, 0.78],
                                    pos: [X0, 520 + li * 42], just: "left" });
        typewriter(ln, 1.95 + li * 0.17, 180, LOG[li].length);
    }

    // カーソル（依頼文のタイプ位置に追従 → 待機中は点滅 → ログが流れ始めたら消える）
    var cur = shapeLayer(s1, "cursor");
    var cc = shapeGroup(cur);
    rect(cc, [26, 56]);
    fill(cc, CYAN);
    T(cur, "ADBE Position").expression =
        "var n=Math.min(" + REQ.length + ",Math.max(0,Math.floor((time-" + RT0 + ")*" + RCPS + ")));[" + X0 + "+n*" + JADV + "+14,425]";
    T(cur, "ADBE Opacity").expression =
        "var e=" + (RT0 + REQ.length / RCPS).toFixed(3) + "; time>1.95?0:((time>" + RT0 + "&&time<e)?100:(Math.floor(time*2.6)%2==0?100:0))";

    // REC 表示
    var rec = shapeLayer(s1, "rec");
    var rc = shapeGroup(rec);
    ellipse(rc, [16, 16]);
    fill(rc, [1, 0.15, 0.2]);
    T(rec, "ADBE Position").setValue([132, 112]);
    T(rec, "ADBE Opacity").expression = "Math.floor(time*2)%2==0?100:15";
    txt(s1, "REC   ONE-PROMPT FILM", { font: MONO, size: 22, color: [0.75, 0.78, 0.85], pos: [152, 112], just: "left" });

    // グリッチ（3.25 / 3.55 / 3.8）＋ 末尾のズームブラーでスマッシュカットへ
    var adj = adjustment(s1, "glitch");
    var td_ = fxAdd(adj, "ADBE Turbulent Displace");
    var amt = td_.property("Amount");
    var ca = fxAdd(adj, "ec.vr.chromaticaberrations");
    var tr = fxAdd(adj, "ADBE Geometry2");
    var G = [3.25, 3.55, 3.8];
    var amtK = [[0, 0]], caK = [[0, 0]], posK = [[0, [960, 540]]];
    for (var i = 0; i < G.length; i++) {
        amtK.push([G[i], 90]); amtK.push([G[i] + 2 / FPS, 40]); amtK.push([G[i] + 4 / FPS, 0]);
        caK.push([G[i], 70]); caK.push([G[i] + 4 / FPS, 0]);
        posK.push([G[i], [960 + (i % 2 ? -40 : 55), 540 + (i - 1) * 12]]); posK.push([G[i] + 1 / FPS, [940, 545]]); posK.push([G[i] + 3 / FPS, [960, 540]]);
    }
    kf(amt, amtK, "hold");
    kf(ca.property("Aberration (Red)"), caK, "hold");
    kf(ca.property("Aberration (Blue)"), caK.map(function (k) { return [k[0], -k[1]]; }), "hold");
    kf(tr.property("Position"), posK, "hold");
    var zb = fxAdd(adj, "ADBE Radial Blur");
    zb.property("Type").setValue(2);
    kf(zb.property("Amount"), [[3.82, 0], [4.0, 80]], "in");
    tr.property("Uniform Scale").setValue(0);
    kf(tr.property("Scale Height"), [[3.82, 100], [4.0, 260]], "in");
    kf(tr.property("Scale Width"), [[3.82, 100], [4.0, 260]], "in");
})();

// ======================================================================
// S4: キネティックタイポ（16〜24s / ローカル 0〜8s）
// ======================================================================
var s4 = app.project.items.addComp("S4_Typo", W, H, 1, 8, FPS);
s4.bgColor = [0.0, 0.0, 0.0];
var S4HITS = [0.5, 1.0, 2.0, 2.5, 3.0, 4.0, 4.5, 5.0, 5.5, 6.0];
(function () {
    solid(s4, [0.005, 0.006, 0.01], "bg");
    // 同心円リング（ビートで脈動）
    var rings = shapeLayer(s4, "rings");
    var rcn = shapeGroup(rings);
    ellipse(rcn, [260, 260]);
    stroke(rcn, CYAN, 2);
    var rep = rcn.addProperty("ADBE Vector Filter - Repeater");
    rep.property("ADBE Vector Repeater Copies").setValue(9);
    var rtr = rep.property("ADBE Vector Repeater Transform");
    rtr.property("ADBE Vector Position").setValue([0, 0]);
    rtr.property("ADBE Vector Scale").setValue([135, 135]);
    rtr.property("endOpacity").setValue(0);
    T(rings, "ADBE Scale").expression = "var p=Math.pow(1-((time*2)%1),4); var s=100+10*p; [s,s]";
    T(rings, "ADBE Rotate Z").expression = "time*12";
    kf(T(rings, "ADBE Opacity"), [[0.3, 0], [0.6, 35], [6.9, 35], [7.0, 0]], "linear");

    // マッチカット: S3 のポータルと同じ径の白い円 → 収縮 → 衝撃波リング
    var dot = shapeLayer(s4, "match_circle");
    var dc = shapeGroup(dot);
    var de = ellipse(dc, [PORTAL_D, PORTAL_D]);
    fill(dc, WHITE);
    kf(de.property("ADBE Vector Ellipse Size"), [[0, [PORTAL_D, PORTAL_D]], [0.12, [PORTAL_D * 1.08, PORTAL_D * 1.08]], [0.48, [0, 0]]], "in");
    var sw = shapeLayer(s4, "shock");
    var swc = shapeGroup(sw);
    var swe = ellipse(swc, [10, 10]);
    var sws = stroke(swc, CYAN, 24);
    kf(swe.property("ADBE Vector Ellipse Size"), [[0.45, [10, 10]], [1.0, [2400, 2400]]], "out");
    kf(sws.property("ADBE Vector Stroke Width"), [[0.45, 30], [1.0, 0]], "linear");
    span(sw, 0.45, 1.05);

    function word(s, t0, t1, o) {
        o.pos = o.pos || [W / 2, H / 2];
        var l = txt(s4, s, o);
        span(l, t0, t1);
        kf(T(l, "ADBE Scale"), [[t0, [o.from || 118, o.from || 118]], [t0 + 0.18, [100, 100]]], "out");
        return l;
    }
    // 事実だけで構成: 1行の依頼 → 6ショット → 4ツール → 1,245フレーム → 手で打ったキーフレーム 0
    function sub(s, t0, t1, y, color) {
        var l = txt(s4, s, { font: JP_B, size: 46, pos: [W / 2, y], color: color || CYAN, tracking: 80 });
        span(l, t0, t1);
        charAnim(l, { opacity: 0 }, t0 + 0.04, t0 + 0.22, { smooth: 0 });
        return l;
    }
    word("1行", 0.5, 1.0, { font: JP_B, size: 400, pos: [W / 2, 480] });
    sub("の依頼から", 0.5, 1.0, 800);
    var wbg = solid(s4, WHITE, "white_bg"); span(wbg, 1.0, 1.5);
    word("6", 1.0, 1.5, { size: 460, color: BLACK, pos: [W / 2, 470] });
    sub("つのショットを設計し", 1.0, 1.5, 800, BLACK);
    word("4", 1.5, 2.0, { size: 300, from: 100, pos: [W / 2, 440] });
    sub("つのツールで作る", 1.5, 2.0, 700);
    var tools = txt(s4, "Blender  ·  EffectCraft  ·  numpy  ·  ffmpeg", { font: MONO, size: 30, pos: [W / 2, 790], color: [0.7, 0.75, 0.85] });
    span(tools, 1.5, 2.0);
    charAnim(tools, { opacity: 0 }, 1.55, 1.8, { smooth: 0 });
    var fr = word("1,245", 2.0, 2.5, { size: 380, tracking: -20, pos: [W / 2, 470] });
    var zc = fxAdd(fr, "ec.vr.chromaticaberrations");
    kf(zc.property("Aberration (Red)"), [[2.0, 60], [2.25, 8]], "out");
    kf(zc.property("Aberration (Blue)"), [[2.0, -60], [2.25, -8]], "out");
    sub("フレームをレンダリング", 2.0, 2.5, 800);
    word("手で打ったキーフレーム", 2.5, 3.0, { font: JP_B, size: 140, color: [0.85, 0.85, 0.9] });
    span(drawLine(s4, 545, 1560, MAGENTA, 2.62, 2.8), 2.5, 3.0);
    var zero = word("0", 3.0, 4.0, { size: 620, from: 100, pos: [W / 2, 470] });
    charAnim(zero, { position: [0, -420, 0], opacity: 0, blur: [0, 60] }, 3.0, 3.3, { ease: "out" });
    charAnim(zero, { position: [0, 600, 0], rotation: 30, opacity: 0 }, 3.75, 4.0, { mode: "out", ease: "in" });
    var z2 = sub("動きはすべてコードが生成", 3.1, 4.0, 830);
    charAnim(z2, { opacity: 0 }, 3.75, 3.95, { mode: "out", smooth: 0 });

    // 4.0 BLENDER / 4.5 × / 5.0 EFFECTCRAFT / 5.5 × / 6.0 CLAUDE OPUS 5.5 — それぞれの役割を添える
    var bl = word("BLENDER", 4.0, 4.5, { size: 260, color: ORANGE, tracking: 20, pos: [W / 2, 480] });
    bl.threeDLayer = true;
    kf(T(bl, "ADBE Rotate Y"), [[4.0, -80], [4.3, 0]], "out");
    sub("3D：光柱・トンネル・コア・ロゴ", 4.05, 4.5, 720, [0.95, 0.75, 0.55]);
    var x1 = word("×", 4.5, 5.0, { size: 360, font: SANS_L });
    kf(T(x1, "ADBE Rotate Z"), [[4.5, -90], [4.75, 0]], "out");
    var ecw = word("EFFECTCRAFT", 5.0, 5.5, { size: 200, color: [0.75, 0.35, 1.0], tracking: 10, pos: [W / 2, 480] });
    charAnim(ecw, { tracking: 200, opacity: 0 }, 5.0, 5.3, { ease: "out" });
    sub("合成・文字・トランジション・色", 5.05, 5.5, 700, [0.82, 0.65, 1.0]);
    var x2 = word("×", 5.5, 6.0, { size: 360, font: SANS_L });
    kf(T(x2, "ADBE Rotate Z"), [[5.5, 90], [5.75, 0]], "out");

    // パーティクルバースト
    var pw = solid(s4, BLACK, "burst");
    span(pw, 6.0, 7.0);
    var cpw = fxAdd(pw, "ec.sim.ccparticleworld");
    kf(cpw.property("Birth Rate"), [[6.0, 6.0], [6.08, 0.0]], "hold");
    pw.blendingMode = BlendingMode.ADD;
    var op5 = word("CLAUDE OPUS 5.5", 6.0, 7.0, { size: 210, tracking: -10, from: 150, pos: [W / 2, 470] });
    var og = fxAdd(op5, "ADBE Glo2");
    og.property("Glow Radius").setValue(60);
    kf(og.property("Glow Intensity"), [[6.0, 4.0], [6.4, 1.0]], "out");
    var ls = fxAdd(op5, "ec.generate.cclightsweep");
    kf(ls.property("Center"), [[6.15, [200, 540]], [6.8, [1750, 540]]], "ease");
    ls.property("Width").setValue(80);
    ls.property("Sweep Intensity").setValue(90);
    span(drawLine(s4, 640, 1100, CYAN, 6.1, 6.35), 6.0, 7.0);
    sub("設計・コード・作曲・編集をすべて担当", 6.1, 7.0, 730, WHITE);

    // 7.0〜8.0 モンタージュ: チートシート 24 技法を 1 秒で。この映像で使ったものだけ点灯
    var NAMES = [["01", "PAN", "パン"], ["02", "TILT", "ティルト"], ["03", "DOLLY IN", "ドリーイン"], ["04", "ZOOM IN", "ズームイン"],
        ["05", "TRACKING", "トラッキング"], ["06", "ORBIT", "オービット"], ["07", "CRANE UP", "クレーンアップ"], ["08", "DOLLY ZOOM", "ドリーズーム"],
        ["09", "RACK FOCUS", "ラックフォーカス"], ["10", "HANDHELD", "手持ち風"], ["11", "FPV", "FPV"], ["12", "DUTCH ANGLE", "ダッチアングル"],
        ["13", "SLOW MOTION", "スローモーション"], ["14", "SPEED RAMP", "スピードランプ"], ["15", "TIME-LAPSE", "タイムラプス"], ["16", "FREEZE FRAME", "フリーズフレーム"],
        ["17", "JUMP CUT", "ジャンプカット"], ["18", "MATCH CUT", "マッチカット"], ["19", "WHIP PAN", "ホイップパン"], ["20", "CROSS DISSOLVE", "クロスディゾルブ"],
        ["21", "WIPE", "ワイプ"], ["22", "SMASH CUT", "スマッシュカット"], ["23", "J-CUT", "Jカット"], ["24", "L-CUT", "Lカット"]];
    var UNUSED = { "01": 1, "02": 1, "03": 1, "04": 1, "05": 1, "13": 1, "15": 1 };
    var head = txt(s4, "カメラワーク 24 技法のうち、この映像で使ったのは 17", { font: JP_B, size: 34, pos: [W / 2, 250], color: [0.75, 0.8, 0.9], tracking: 60 });
    span(head, 7.0, 8.0);
    var mEn = txt(s4, "PAN", { size: 190, pos: [W / 2, 520], tracking: -10, name: "montage_en" });
    var mJp = txt(s4, "パン", { font: JP_B, size: 56, pos: [W / 2, 700], color: CYAN, name: "montage_jp" });
    var mNo = txt(s4, "01 / 24", { font: MONO_B, size: 34, pos: [W / 2, 360], color: [0.6, 0.65, 0.75], name: "montage_no" });
    var mSt = txt(s4, "未使用", { font: JP_B, size: 32, pos: [W / 2, 800], color: CYAN, name: "montage_status" });
    var spEn = mEn.property("ADBE Text Properties").property("ADBE Text Document");
    var spJp = mJp.property("ADBE Text Properties").property("ADBE Text Document");
    var spNo = mNo.property("ADBE Text Properties").property("ADBE Text Document");
    var spSt = mSt.property("ADBE Text Properties").property("ADBE Text Document");
    for (var i = 0; i < NAMES.length; i++) {
        var t = 7.0 + i / 24;
        var used = !UNUSED[NAMES[i][0]];
        var d1 = spEn.value; d1.text = NAMES[i][1]; d1.fillColor = used ? WHITE : [0.3, 0.32, 0.36]; spEn.setValueAtTime(t, d1);
        var d2 = spJp.value; d2.text = NAMES[i][2]; d2.fillColor = used ? CYAN : [0.3, 0.32, 0.36]; spJp.setValueAtTime(t, d2);
        var d3 = spNo.value; d3.text = NAMES[i][0] + " / 24"; spNo.setValueAtTime(t, d3);
        var d4 = spSt.value; d4.text = used ? "✓ この映像で使用" : "未使用"; d4.fillColor = used ? CYAN : [0.4, 0.42, 0.46]; spSt.setValueAtTime(t, d4);
    }
    var mlay = [mEn, mJp, mNo, mSt];
    for (var j = 0; j < mlay.length; j++) {
        span(mlay[j], 7.0, 8.0);
        try {
            var ptx = mlay[j].property("ADBE Text Properties").property("ADBE Text Document");
            for (var k = 1; k <= ptx.numKeys; k++) ptx.setInterpolationTypeAtKey(k, KeyframeInterpolationType.HOLD);
        } catch (e) { }
    }
    kf(T(mEn, "ADBE Scale"), [[7.0, [80, 80]], [8.0, [125, 125]]], "in");

    // ヒットごとのカメラシェイク
    var sh = adjustment(s4, "shake");
    var trs = fxAdd(sh, "ADBE Geometry2");
    trs.property("Position").expression =
        "var h=[" + S4HITS.join(",") + "]; var a=0; for(var i=0;i<h.length;i++){ if(time>=h[i]) a=Math.max(a,22*Math.exp(-(time-h[i])*16)); }" +
        "[960+a*Math.sin(time*97), 540+a*Math.cos(time*83)]";
})();

// ======================================================================
// HUD（技法ラベル＋タイムコード）
// ======================================================================
var hud = app.project.items.addComp("HUD", W, H, 1, DUR, FPS);
(function () {
    var LABELS = [
        [0.4, 3.0, "10", "HANDHELD", "わざと小さく揺らす"],
        [3.0, 4.0, "23", "J-CUT", "次の場面の音が先に聞こえる"],
        [4.0, 4.8, "22", "SMASH CUT", "静かな場面から急に切り替える"],
        [4.8, 9.8, "08", "DOLLY ZOOM", "人物はそのまま背景だけ伸び縮み"],
        [9.8, 10.6, "19", "WHIP PAN", "素早く振ってブレで次へ"],
        [10.6, 12.6, "11", "FPV DRONE SHOT", "ドローンで突き進む疾走感"],
        [12.6, 13.4, "14", "SPEED RAMP", "速い→遅いと速さを変える"],
        [13.4, 15.6, "12", "DUTCH ANGLE", "画面を斜めに傾ける"],
        [15.6, 16.6, "18", "MATCH CUT", "形や動きをそろえて場面を変える"],
        [16.6, 23.0, "17", "JUMP CUT", "同じ画角のまま時間を飛ばす"],
        [23.85, 24.6, "21", "WIPE", "境目が横切って画面が入れ替わる"],
        [24.6, 25.4, "06", "ORBIT", "被写体の周りを回り込む"],
        [25.4, 28.0, "09", "RACK FOCUS", "ピントを手前から奥へ送る"],
        [28.0, 28.5, "16", "FREEZE FRAME", "動きを一瞬止める"],
        [28.5, 31.6, "06", "ORBIT", "被写体の周りを回り込む"],
        [31.6, 33.2, "20", "CROSS DISSOLVE", "前後の映像を重ねて溶かす"],
        [33.2, 37.6, "07", "CRANE UP", "カメラが上へ昇っていく"],
        [37.6, 40.0, "24", "L-CUT", "前の場面の音が後まで残る"]
    ];
    var X = 120, Y = 968;
    for (var i = 0; i < LABELS.length; i++) {
        var L = LABELS[i], t0 = L[0], t1 = L[1];
        var bar = shapeLayer(hud, "bar" + L[2]);
        var bc = shapeGroup(bar);
        rect(bc, [4, 58]);
        fill(bc, CYAN);
        T(bar, "ADBE Position").setValue([X - 18, Y + 6]);
        kf(T(bar, "ADBE Scale"), [[t0, [100, 0]], [t0 + 0.12, [100, 100]]], "out");
        span(bar, t0, t1);
        var no = txt(hud, L[2], { font: MONO_B, size: 26, color: CYAN, pos: [X, Y - 8], just: "left" });
        var en = txt(hud, L[3], { font: MONO_B, size: 26, color: WHITE, pos: [X + 56, Y - 8], just: "left", tracking: 60 });
        var jp = txt(hud, L[4], { font: JP, size: 20, color: [0.7, 0.74, 0.82], pos: [X, Y + 26], just: "left" });
        var parts = [no, en, jp];
        for (var j = 0; j < parts.length; j++) {
            span(parts[j], t0, t1);
            var n = j === 1 ? L[3].length : (j === 0 ? 2 : L[4].length);
            charAnim(parts[j], { opacity: 0 }, t0 + j * 0.04, t0 + j * 0.04 + Math.min(0.35, n / 45), { smooth: 0 });
        }
    }
    // 右上: タイムコード / ショット番号
    var tc = txt(hud, "00:00:00:00", { font: MONO, size: 22, color: [0.75, 0.78, 0.85], pos: [W - 120, 112], just: "right" });
    tc.property("ADBE Text Properties").property("ADBE Text Document").expression =
        "var f=Math.round(time*30); function p(n){return (n<10?'0':'')+n;} " +
        "'TC ' + p(Math.floor(f/108000)) + ':' + p(Math.floor(f/1800)%60) + ':' + p(Math.floor(f/30)%60) + ':' + p(f%30)";
    span(tc, 0.0, 40.0);
    var shot = txt(hud, "SHOT 01/06", { font: MONO, size: 22, color: [0.5, 0.55, 0.65], pos: [W - 120, 146], just: "right" });
    shot.property("ADBE Text Properties").property("ADBE Text Document").expression =
        "var b=[0,4,10,16,24,32]; var n=1; for(var i=0;i<b.length;i++) if(time>=b[i]) n=i+1; 'SHOT 0'+n+'/06'";
    span(shot, 0.0, 40.0);
    // 左上（S1 以外）: スタック表記
    var stack = txt(hud, "HOW THIS WAS MADE  /  ALL NUMBERS ARE REAL", { font: MONO, size: 20, color: [0.55, 0.6, 0.7], pos: [120, 112], just: "left", tracking: 40 });
    span(stack, 4.0, 40.0);
    charAnim(stack, { opacity: 0 }, 4.1, 4.6, { smooth: 0 });
})();

// ======================================================================
// MAIN
// ======================================================================
var main = app.project.items.addComp("Main", W, H, 1, DUR, FPS);
main.bgColor = BLACK;
main.motionBlur = true;

// --- 下から順に積む（addXxx は最上位に追加される） ---
var aud = main.layers.add(fAudio);
aud.startTime = 0;

// S1
var L1 = main.layers.add(s1);
L1.startTime = 0;
T(L1, "ADBE Position").expression = "wiggle(1.3, 7)";
T(L1, "ADBE Rotate Z").expression = "wiggle(1.0, 0.35)";
kf(T(L1, "ADBE Scale"), [[0, [100, 100]], [3.8, [109, 109]]], "linear");

// S2（ドリーズーム）→ ホイップパンで S3 へ
var L2 = main.layers.add(fS2);
L2.startTime = 4.0;
span(L2, 4.0, 10.0);
L2.motionBlur = true;
var g2 = fxAdd(L2, "ADBE Glo2");
g2.property("Glow Threshold").setValue(70);
g2.property("Glow Radius").setValue(50);
g2.property("Glow Intensity").setValue(0.5);
kf(T(L2, "ADBE Position"), [[9.82, [960, 540]], [10.0, [-900, 540]]], "in");
var db2 = fxAdd(L2, "ADBE Motion Blur");
db2.property("Direction").setValue(90);
kf(db2.property("Blur Length"), [[9.82, 0], [10.0, 260]], "in");

var L3 = main.layers.add(fS3);
L3.startTime = 9.84;
span(L3, 9.84, 16.0);
L3.motionBlur = true;
// ホイップパン: S2 が左へ抜けると同時に S3 が右から滑り込む
kf(T(L3, "ADBE Position"), [[9.84, [2880, 540]], [10.03, [960, 540]]], "out");
var g3 = fxAdd(L3, "ADBE Glo2");
g3.property("Glow Threshold").setValue(70);
g3.property("Glow Radius").setValue(40);
g3.property("Glow Intensity").setValue(0.4);
// 15〜16s を僅かにスローにし、ポータルが円に見える最後のフレーム(f172)で S3 を終える
L3.timeRemapEnabled = true;
var tr3 = L3.property("ADBE Time Remapping");
while (tr3.numKeys > 0) tr3.removeKey(1);
// 滑り込み中（方向ブラーで見えない）は先頭フレームを保持し、10.0s から音楽・HUD と同じ位相で再生
kf(tr3, [[9.84, 0.0], [10.0, 0.0], [15.0, 5.0], [15.967, 171 / 30]], "linear");
tr3.setInterpolationTypeAtKey(1, KeyframeInterpolationType.HOLD);
span(L3, 9.84, 16.0);
try { L3.frameBlendingType = FrameBlendingType.PIXEL_MOTION; } catch (e) { }
var db3 = fxAdd(L3, "ADBE Motion Blur");
db3.property("Direction").setValue(90);
kf(db3.property("Blur Length"), [[9.84, 260], [10.25, 0]], "out");

// S5（オービット / フリーズフレーム / 爆散）— タイムリマップ
var L5 = main.layers.add(fS5);
L5.startTime = 24.0;
L5.timeRemapEnabled = true;
var trm = L5.property("ADBE Time Remapping");
while (trm.numKeys > 0) trm.removeKey(1);
kf(trm, [[24.0, 0.0], [28.0, 4.0], [28.5, 4.0], [32.5, 7.966]], "linear");
trm.setInterpolationTypeAtKey(2, KeyframeInterpolationType.HOLD);
span(L5, 24.0, 32.5);
// フリーズ中: 彩度を落としてコントラストを上げ、わずかに寄る
var hs5 = fxAdd(L5, "ADBE HUE SATURATION");
kf(hs5.property("Master Saturation"), [[24.0, 10], [28.0, -100], [28.5, 10]], "hold");
var bc5 = fxAdd(L5, "ADBE Brightness & Contrast 2");
kf(bc5.property("Contrast"), [[24.0, 0], [28.0, 40], [28.5, 0]], "hold");
kf(T(L5, "ADBE Scale"), [[28.0, [100, 100]], [28.5, [104, 104]], [28.52, [100, 100]]], "linear");
// S6 へクロスディゾルブ
kf(T(L5, "ADBE Opacity"), [[31.6, 100], [32.5, 0]], "linear");

// S4 タイポ（S5 の上）→ ワイプで S5 へ
var L4 = main.layers.add(s4);
L4.startTime = 16.0;
span(L4, 16.0, 24.15);
var wp = fxAdd(L4, "ADBE Linear Wipe");
wp.property("Wipe Angle").setValue(90);
wp.property("Feather").setValue(40);
kf(wp.property("Transition Completion"), [[23.88, 0], [24.15, 100]], "in");
// ワイプの境目に光るライン
var wl = shapeLayer(main, "wipe_edge");
var wlc = shapeGroup(wl);
rect(wlc, [10, 1300]);
fill(wlc, CYAN);
kf(T(wl, "ADBE Position"), [[23.88, [-20, 540]], [24.15, [1940, 540]]], "in");
var wlg = fxAdd(wl, "ADBE Glo2");
wlg.property("Glow Radius").setValue(80);
wlg.property("Glow Intensity").setValue(2.0);
span(wl, 23.88, 24.16);

// S6 は S5 の下に置き、S5 のフェードアウトで現れるようにする
var L6 = main.layers.add(fS6);
L6.startTime = 32.0;
span(L6, 32.0, 40.0);
L6.moveAfter(L5);

// --- データカード（右下）: 各ショットの実測値 ---
function countExpr(t0, n, suffix) {
    return "var t=Math.min(1,Math.max(0,(time-" + t0 + ")/0.7)); var e=1-Math.pow(1-t,3); var n=Math.round(" + n + "*e);" +
        "var s=String(n), o=''; while(s.length>3){o=','+s.slice(-3)+o; s=s.slice(0,-3);} s+o+'" + suffix + "'";
}
function dataCard(t0, t1, big, label, detail, count) {
    var X = W - 130;
    // 明るい背景でも読めるよう、ぼかした暗い下敷きを敷く
    var scrim = shapeLayer(main, "card_scrim");
    var scc = shapeGroup(scrim);
    rect(scc, [900, 330]);
    fill(scc, BLACK);
    T(scrim, "ADBE Position").setValue([X - 330, 870]);
    var sb = fxAdd(scrim, "ADBE Gaussian Blur 2");
    sb.property("Blurriness").setValue(90);
    span(scrim, t0, t1);
    kf(T(scrim, "ADBE Opacity"), [[t0, 0], [t0 + 0.2, 62], [t1 - 0.2, 62], [t1, 0]], "linear");
    var ln = shapeLayer(main, "card_line");
    var lc = shapeGroup(ln);
    rect(lc, [440, 2]);
    fill(lc, CYAN);
    T(ln, "ADBE Position").setValue([X - 220, 760]);
    kf(T(ln, "ADBE Scale"), [[t0, [0, 100]], [t0 + 0.3, [100, 100]]], "out");
    var b = txt(main, big, { font: SANS_B, size: 100, pos: [X, 826], just: "right", tracking: -10 });
    if (count) b.property("ADBE Text Properties").property("ADBE Text Document").expression = countExpr(t0, count[0], count[1]);
    var lb = txt(main, label, { font: JP_B, size: 34, color: CYAN, pos: [X, 906], just: "right", tracking: 40 });
    var dt = txt(main, detail, { font: JP, size: 22, color: [0.8, 0.84, 0.92], pos: [X, 954], just: "right", tracking: 20 });
    var all = [ln, b, lb, dt];
    for (var i = 0; i < all.length; i++) {
        span(all[i], t0, t1);
        kf(T(all[i], "ADBE Opacity"), [[t0, 0], [t0 + 0.12, 100], [t1 - 0.2, 100], [t1, 0]], "linear");
    }
    charAnim(b, { opacity: 0, blur: [30, 30] }, t0, t0 + 0.35, { ease: "out" });
    charAnim(lb, { opacity: 0 }, t0 + 0.1, t0 + 0.4, { smooth: 0 });
    charAnim(dt, { opacity: 0 }, t0 + 0.2, t0 + 0.7, { smooth: 0 });
}
dataCard(4.8, 7.2, "22,020", "本の光柱", "Geometry Nodes で生成 ／ 120BPM の拍で波紋が走る", [22020, ""]);
dataCard(7.3, 9.75, "18→96mm", "ドリーズーム", "カメラは 6m→32m 後退、モノリスの大きさは一定", null);
dataCard(10.6, 12.5, "456m", "FPV で飛ぶパス", "六角リング 120 枚 ／ 浮遊する破片 2,500 個", [456, "m"]);
dataCard(12.6, 14.6, "70→8m/s", "スピードランプ", "減速しながら 28° 傾ける（ダッチアングル）", null);
dataCard(14.6, 15.95, "180m/s", "最高速でポータルへ", "抜けた先の白い円が、次のショットの円になる", [180, "m/s"]);
dataCard(24.6, 27.95, "1,550", "粒の光", "3 本のリングが別々の速度で公転 ／ f1.2 でピント送り", [1550, ""]);
dataCard(28.55, 30.95, "270°", "オービット", "8 秒かけて被写体の周りを回り込む", [270, "°"]);
dataCard(31.0, 32.4, "28,909", "個の破片", "球の表面から生成し、法線方向へ飛ばす", [28909, ""]);
dataCard(32.45, 33.95, "28,455", "個のボクセル", "左から順に集まり、文字になる", [28455, ""]);

// --- S3 終端: ポータルへ白飛び ---
// （マッチカットのため白フェードは使わない）

// --- フリーズフレームの演出（ブラケット＋大きなラベル） ---
var frz = txt(main, "FREEZE FRAME", { font: SANS_B, size: 140, pos: [W / 2, 520], tracking: 200 });
span(frz, 28.0, 28.5);
charAnim(frz, { tracking: 600, opacity: 0 }, 28.0, 28.15, { ease: "out" });
var frzj = txt(main, "16 / 動きを一瞬止める", { font: JP_B, size: 34, pos: [W / 2, 640], color: CYAN });
span(frzj, 28.0, 28.5);
var brk = shapeLayer(main, "freeze_frame_box");
var bkc = shapeGroup(brk);
rect(bkc, [1500, 760]);
stroke(bkc, WHITE, 3);
T(brk, "ADBE Position").setValue([W / 2, H / 2]);
kf(T(brk, "ADBE Scale"), [[28.0, [112, 112]], [28.12, [100, 100]]], "out");
span(brk, 28.0, 28.5);

// --- レターボックス（S5 区間でシネスコに） ---
var lbT = solid(main, BLACK, "lb_top", W, 140);
var lbB = solid(main, BLACK, "lb_bottom", W, 140);
kf(T(lbT, "ADBE Position"), [[24.0, [960, -70]], [24.5, [960, 70]], [31.6, [960, 70]], [32.4, [960, -70]]], "ease");
kf(T(lbB, "ADBE Position"), [[24.0, [960, 1150]], [24.5, [960, 1010]], [31.6, [960, 1010]], [32.4, [960, 1150]]], "ease");
span(lbT, 24.0, 32.5);
span(lbB, 24.0, 32.5);

// --- S6: 床を下に向かって沈める（乗算グラデーション）---
var fg6 = solid(main, WHITE, "floor_grade");
var rp6 = fxAdd(fg6, "ADBE Ramp");
rp6.property("Start of Ramp").setValue([960, 600]);
rp6.property("Start Color").setValue([1, 1, 1]);
rp6.property("End of Ramp").setValue([960, 1080]);
rp6.property("End Color").setValue([0.12, 0.13, 0.16]);
fg6.blendingMode = BlendingMode.MULTIPLY;
span(fg6, 32.0, 40.0);

// --- S6: ロゴ実体化の衝撃波 / サブタイトル / タグライン ---
var shock = shapeLayer(main, "logo_shock");
var shc = shapeGroup(shock);
var she = ellipse(shc, [50, 50]);
var shs = stroke(shc, CYAN, 30);
T(shock, "ADBE Position").setValue([W / 2, 525]);
kf(she.property("ADBE Vector Ellipse Size"), [[34.0, [50, 50]], [34.7, [2800, 1000]]], "out");
kf(shs.property("ADBE Vector Stroke Width"), [[34.0, 40], [34.7, 0]], "linear");
shock.blendingMode = BlendingMode.ADD;
span(shock, 34.0, 34.75);

var stx = txt(main, "この映像は、1 行の依頼から AI がコードだけで作りました。", { font: JP_B, size: 36, pos: [W / 2, 705], tracking: 60, color: WHITE });
span(stx, 34.4, 40.0);
charAnim(stx, { opacity: 0, blur: [24, 24] }, 34.4, 35.3, { ease: "out" });
var tag = txt(main, "3D：Blender 5.2　／　合成：EffectCraft 0.4　／　音楽：numpy で合成　／　手で打ったキーフレーム：0", { font: JP, size: 23, pos: [W / 2, 764], tracking: 40, color: [0.72, 0.78, 0.88] });
span(tag, 35.3, 40.0);
charAnim(tag, { opacity: 0 }, 35.3, 36.3, { smooth: 0 });
var lgl = drawLine(main, 662, 520, CYAN, 34.35, 34.7);
span(lgl, 34.35, 40.0);

// 暗転（38.8〜40.0）→ L カットで音だけ残る黒にクレジット
var fade = solid(main, BLACK, "fade");
span(fade, 38.8, DUR);
kf(T(fade, "ADBE Opacity"), [[38.8, 0], [40.0, 100]], "ease");
var cred = txt(main, "made with Claude Opus 5.5  ·  Blender  ·  EffectCraft", { font: MONO, size: 20, pos: [W / 2, 540], color: [0.55, 0.6, 0.7], tracking: 60 });
span(cred, 40.0, DUR);
kf(T(cred, "ADBE Opacity"), [[40.0, 0], [40.4, 100], [41.0, 100], [41.45, 0]], "ease");

// --- フラッシュ（カット点） ---
var fl = solid(main, WHITE, "flash");
fl.blendingMode = BlendingMode.ADD;
kf(T(fl, "ADBE Opacity"), [[0, 0], [3.99, 0], [4.0, 100], [4.25, 0], [27.99, 0], [28.0, 85], [28.1, 0], [28.49, 0], [28.5, 60],
    [28.7, 0], [30.99, 0], [31.0, 100], [31.3, 0], [33.99, 0], [34.0, 100], [34.5, 0]], "linear");

// --- シェイク（インパクト点） ---
var shk = adjustment(main, "shake");
var trk = fxAdd(shk, "ADBE Geometry2");
trk.property("Scale Height").setValue(103);
trk.property("Scale Width").setValue(103);
trk.property("Position").expression =
    "var h=[[4.0,26],[16.0,22],[28.5,14],[31.0,34],[34.0,24]]; var a=0;" +
    "for(var i=0;i<h.length;i++){ if(time>=h[i][0]) a=Math.max(a,h[i][1]*Math.exp(-(time-h[i][0])*7)); }" +
    "[960+a*Math.sin(time*91), 540+a*Math.cos(time*73)]";
span(shk, 4.0, 40.0);

// --- グレード ---
var grade = adjustment(main, "grade");
var bcg = fxAdd(grade, "ADBE Brightness & Contrast 2");
bcg.property("Contrast").setValue(14);
var hsg = fxAdd(grade, "ADBE HUE SATURATION");
hsg.property("Master Saturation").setValue(14);
var cag = fxAdd(grade, "ec.vr.chromaticaberrations");
cag.property("Aberration (Red)").setValue(4);
cag.property("Aberration (Blue)").setValue(-4);
var vig = fxAdd(grade, "ec.stylize.ccvignette");
vig.property("Amount").setValue(40);
var grn = fxAdd(grade, "VISINF Grain Implant");
grn.property("Tweaking").property("Intensity").setValue(0.45);
grn.property("Tweaking").property("Size").setValue(1.2);

// HUD は最前面（グレードやシェイクの影響を受けない）
var LH = main.layers.add(hud);
LH.startTime = 0;
T(LH, "ADBE Opacity").setValue(85);

writeLn("built: layers=" + main.numLayers + " items=" + app.project.numItems);
