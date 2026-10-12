// プロジェクト内の全キーフレーム数を数える（ログ表示用の実数）
var total = 0;
function walk(p) {
    for (var i = 1; i <= p.numProperties; i++) {
        var q = p.property(i);
        if (q.numProperties) walk(q);
        else if (q.numKeys) total += q.numKeys;
    }
}
for (var i = 1; i <= app.project.numItems; i++) {
    var it = app.project.item(i);
    if (!(it instanceof CompItem)) continue;
    for (var j = 1; j <= it.numLayers; j++) walk(it.layer(j));
}
total;
