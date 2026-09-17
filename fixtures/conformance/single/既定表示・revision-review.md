# 既定表示・revision fixture review

2026-09-14。matrix §6.11のうち7件（SINGLE-104-02/03/04、105-01/02、106-04/05）を追加する。
Markdown byte一致を要する104-01と、新しいContext corpusとgolden Digestを要する106-01/02/03は同節の残件とする。
根拠は[結果・Diagnostic・終了コード](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)§7、
[doctor仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md)、
[verify仕様](../../../docs/03.詳細設計/03_操作仕様/03_verify.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDである。

| ID | 操作 | 唯一の条件 | status／終了コード | 既存fixtureとの差分 |
|---|---|---|---|---|
| SINGLE-104-02 | check | `--format`省略 | passed／0 | SINGLE-075-01からoption指定を外す |
| SINGLE-104-03 | verify | `--format`省略 | passed／0 | SINGLE-055の入力でtext出力 |
| SINGLE-104-04 | doctor | `--format`省略 | passed／0 | SINGLE-001の入力でtext出力 |
| SINGLE-105-01 | context | commitのあるrepository | passed／0 | SINGLE-042へbase commitを足す |
| SINGLE-105-02 | verify | Git不在 | passed／0 | SINGLE-055からGitを外す |
| SINGLE-106-04 | verify | 出力のないcommand | passed／0 | SINGLE-069-01のscriptを無出力へ替える |
| SINGLE-106-05 | verify | 2 targetに同じ条件 | failed／1 | 不在の明示起点2件 |

各fixtureは査読済みcorpusと期待結果を再利用し、表示または環境の性質を1つだけ変える。
104-02/03/04は`--format`を渡さず、既定値がcheck・verify・doctorでtextであることを固定する。
要約行は固定文字列で持つが、監査はJSON対応物から導出式どおりに再計算して照合する。
targetsはcheckが`checkedDocumentCount`、verifyが`targetResults`の件数、doctorが`checks`の件数であり、
diagnosticsは最上位とtarget上のDiagnosticの総数である。doctorだけが`scope=`を出さないことも検査する。

105-01はSINGLE-042との差分をbase commitだけにし、`revision`を現在版の`commit`と`dirty`に固定する。
期待JSONのcommitは他fixtureと同じ0埋めのplaceholderとし、監査は隔離setupの実HEADが40桁小文字16進であること、
worktreeが清潔であること、operationごとのrevision形（checkは`base`を含む）を実際に観測して確かめる。
105-02はGitを初期化せず、`PATH=/dev/null`で呼び出す。Git不在だけを理由とするDiagnosticは返さず、
`revision`はnullのままである。副作用snapshotの`git`もnullとし、成功した空のGit statusで代用しない。

106-04はSINGLE-069-01と同じcorpus・同じcommand pathで、scriptだけを無出力へ替える。
scriptの本文はDigest材料ではないため、target Digestは同じ値になる。監査はfixture自身のscriptを実行し、
終了コード0と両stream空を観測してから、抜粋が空でtruncatedがfalseであることを固定する。
106-05は構文上妥当で不在の明示起点2件を渡し、同じ`CTX-ROOT-MISSING-001`を両targetへ独立に生じさせる。
targetのDigestはnull、`bindingRefs`と`commands`は空で、textの`diagnostics`は2である。
`source.kind`が`file`以外のtext行は先頭fieldに`invocation`を置き、path・line・columnを空fieldのまま残す。
この空field規則は結果契約§7へ追記し、review台帳のsource hashを更新した。
あわせて、base commitへ明示`--base`を要求する監査規則を`check`だけに限定した。`context`と`verify`は
`--base`を持たないため、従来の規則ではcommit済みcontext fixtureを表現できなかった。

入力byte列・実行bit・manifest・完全結果・text・副作用Schemaを検証し、隔離Git repositoryを2回setupして
固定snapshotへ照合する。Digestを持つ結果は入力treeからの独立計算と一致することも確かめる。
回帰試験は要約行の件数・scope有無・Diagnostic行数の改変、revisionの有無と形、truncated flag、target件数、
副作用の許容、無出力scriptへの出力追加を拒否する。
renderer、Git reader、Coreは実装も実行もしない。実際の既定出力と観測revisionはGate Bで受け入れる。
