# 明示report fixture review

[適合fixture仕様 §6.7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#67-出力とreport)の
`SINGLE-071-01/02/03/04`と`SINGLE-072`を扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 副作用Schemaを拡張する必要があった

これまでのfixtureはすべて`policy: "read-only"`で`before == after`であり、正当にfileを作る実行を表現できなかった。
`side-effects.schema.json`は現在、`report` objectを伴う`policy: "explicit-report"`を受け付け、両者を対にする。
`explicit-report`は`report`を必須とし、`read-only`はこれを禁止する。

report file名は生成時刻と連番を含み
（[結果・Diagnostic・終了コード §8](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#8-report)）、
共通normalizerはちょうどそれを除外するので、作成されるfileをsnapshotで名指しできない。そのため`before`と`after`は
既に存在したpathだけを記述し（それらはすべて不変でなければならない）、`report` objectが差分を持つ。directory、
作成件数、名前のpattern、一時fileが残らないことである。

```json
{"directory": ".spec/reports", "createdCount": 1,
 "namePattern": "^[0-9]{8}T[0-9]{6}Z-(?:check|verify)(?:-[1-9][0-9]*)?\\.json$",
 "temporaryFilesRemaining": 0}
```

監査はpatternを鵜呑みにしない。正しい形式の名前を受理し、時刻の欠落、0の連番、異なる操作名、残った`.tmp`接尾辞を
拒否することを要求する。patternを`^.*$`へ緩めたfixtureは拒否する。

## 排他的な作成には、衝突し得る既存fileが必要である

`SINGLE-071-*`の入力には、report非作成の群で導入した`.spec/reports/existing.json`を残す。空のdirectoryへreportを
作るだけでは、排他的な作成と置換を区別できない。既存のreportがある状態で`before == after`なら古いreportは無傷で残り、
`createdCount: 1`なら新しいreportがその隣に現れたことになる。snapshotからこのfileが消えたfixtureは監査が拒否する。

4件で両操作の両結果を扱い、`SINGLE-070-*`の組のreview済みの結果を直接使う。reportを保存しても、計算済みの結果は
変わらない。書き直すと、2つの群がずれる原因を作るだけである。

## `SINGLE-072`は意図して失敗するcheckに基づく

matrixは、保存先が使えない場合も「元結果」を端末へ返すことを求める。*成功する*checkに基づくと、保持すべき元の
Diagnosticがなく、この性質は空疎になる。そのため、結果に既に`SPEC-RELATION-MISSING-001`を持つ`SINGLE-070-02`に
基づく。期待値は、結果の本体が変わらず、元のDiagnosticが残り、`SPEC-REPORT-WRITE-001`が追加され、statusが
`failed`から`error`へ上がることである。監査は元のfixtureとfieldごとに比べ、Diagnosticを持たない元のfixtureを拒否する。

**保存先は、directoryの権限ではなく通常fileで塞ぐ。** Gitはdirectoryの権限を記録しないので、`0o555`のreport
directoryはfresh checkoutで失われ、fixtureは知らないうちに何も検査しなくなる。`.spec/reports`に通常fileを置けば
version管理でき、同じ理由でdirectoryを使えなくできる。監査は、setup後もそれが通常fileであること、`SINGLE-071-*`が
本物のdirectoryを持つことを確認する。

## 限界

- Coreは実行していない。作成したfileが結果JSONであること、同じ秒に衝突した場合も本当に排他的に作成することを含め、
  Coreとの一致はGate Bで判定する。
- patternは連番の接尾辞を受理するが、それを生むfixtureはない。同じ秒の衝突には2回の実行が必要であり、1回の起動だけを
  持つfixtureでは表現できない。
- `SINGLE-072`は、保存先を使えなくする方法を1つだけ固定する。読取り専用のdirectory、空きのないfilesystem、権限の
  errorは、このmatrixでは区別しない。
