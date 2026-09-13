# TASK境界・対象選択fixtureレビュー

2026-09-14。SINGLE-034、SINGLE-035-01〜02の3件について、同じ入力を異なるcheck scopeで検査する
完全期待値を固定する。Coreの実行結果ではない。

## 入力と期待値

全件のHEADに最小設定、open TASK-001、src/inside.py、src2/outside.pyを置く。
TASKのchangesは[src/]だけで、関係や規範文を持たない。HEADからTASKのObjectiveへの説明追記と
src2/outside.pyのcomment変更だけを未stageで行う。src/inside.pyは存在するが変更しない。
3件の入力・Git状態は同一とし、呼出し方による差を固定する。

| ID | 呼出し（共通で --base HEAD --format json） | 期待値 |
|---|---|---|
| SINGLE-034 | check TASK-001 | selected、failed / 1、SPEC-TASK-BOUNDARY-001が1件 |
| SINGLE-035-01 | check | changed、passed / 0、Diagnosticなし |
| SINGLE-035-02 | check --full | full、passed / 0、Diagnosticなし |

034はsrc/とsrc2/をsegment境界で区別し、src2/outside.pyだけを境界外とする。
TASK自身の変更は境界比較対象から除外されるため、2件目のDiagnosticを追加しない。
sourceは違反したfileのworkspaceId=root、path=src2/outside.pyとし、summaryはexpected/check.jsonの値に固定する。
line、key、evidence、suggestedActionは付加しない。このsource位置と文言は今回の受入期待値として選択した値である。

035-01ではTASKの説明変更により、引数なしでもTASKが確実に選ばれる。変更path数は2、対象文書数は1、
未所有code/testの除外path数は1。TASKのchangesはcode所有逆索引を作らない。
境界を検査しないことや未所有codeの存在をwarningにしない。035-02も全体文書検査だけを行う。
selected/fullでは完全検査文書数1、規範文数0とし、changedだけにselectionを出力する。
全件のrevisionはHEADの代表値とdirty=true、durationMs=0で、既存normalizer以外の比較除外は追加しない。

根拠は[check仕様 §3・§5〜§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[Frontmatter仕様 §3](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合matrix §6.4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証の範囲

task_fixtures.pyはレビュー済みの固定byte列、manifest、完全期待JSON、Frontmatter Schema、read-only副作用期待値を照合する。
各2回の隔離setupでHEAD/indexのpathとblob、worktreeの全file byte列、Git status/index、HOME/cache/TMPDIRを確認する。
本番のtarget選択やpath境界判定、汎用YAML解析は実装しない。

回帰試験では境界違反の成功化、sourceのsrc/への変更、明示TASK指定の除去、対象・除外件数の誤り、
fullへのwarning混入、規範文数の誤り、副作用期待値の変更、許可範囲の拡大、TASK選択原因の消去を拒否する。
実repositoryの変更をstage/commitした場合にもHEAD/index照合が失敗することを確認する。
Coreの実stdout、終了コード、境界判定、実副作用はGate Bで受け入れる。

準備済みは53/311件、残258件。golden Digest等とfresh checkoutからの全Gate A検証は未完了であり、
Gate AはBlockedを維持する。
