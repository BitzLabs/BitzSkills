# Core副作用fixtureレビュー

2026-09-17。SINGLE-125-01〜05の5件を追加する。SINGLE-125-06は発生条件が未確定のため含めない（後述）。
根拠は[適合fixture仕様 §5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#5-副作用の検査)、
[安全な入出力 §2](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#2-読取りと書込み)、
[結果・Diagnostic・終了コード §8](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#8-report)である。

| ID | source fixture | 実行 | status／終了コード | 副作用policy |
|---|---|---|---|---|
| SINGLE-125-01 | SINGLE-042 | `context REQ-001 --purpose verify --format json` | passed／0 | read-only |
| SINGLE-125-02 | SINGLE-001 | `doctor --format json` | passed／0 | read-only |
| SINGLE-125-03 | SINGLE-070-01 | `check --full --base HEAD --format json` | passed／0 | read-only |
| SINGLE-125-04 | SINGLE-055 | `verify REQ-001 --format json` | passed／0 | read-only |
| SINGLE-125-05 | SINGLE-071-01 | `check --full --base HEAD --format json --report` | passed／0 | explicit-report（1件） |

各caseは、別moduleで監査済みのsource fixtureと同じ起動・入力・期待結果を使う。manifestは`fixtureId`と
`description`だけを差し替え、期待結果fileはsourceとbyte一致させる。副作用の観点で結果を変えないためである。

125-01〜04は`.spec/reports/`を置かない。125-03はsourceから既存reportだけを除く。これにより、Coreが
report directory、一時file、cache、lock fileを暗黙作成すると、repository snapshotの差分として失敗する。
既存reportの不変はSINGLE-070系が既に固定しているため、ここでは「何も増えない」ことを主眼にする。
HOME、`XDG_CACHE_HOME`、`TMPDIR`はharnessが割り当てる空directoryであり、before／afterとも空で固定する。
manifestの`env`は空とし、fixture側から別の保存先を与えない。
125-04のtest commandは`["/bin/true", "{tests}"]`に限定し、test process自身の書込みと分離する。

125-05はSINGLE-071-01の副作用期待と同じで、既存report `existing.json`を不変に保ったまま、
規定名patternに合う最終report 1件だけを許し、一時file残存0件を要求する。

auditは各fixtureを隔離repositoryへ2回setupし、固定snapshotと相互の一致を確認する。
回帰試験では、cacheへの書込み許容、HOMEの事前汚染、read-only caseへの`--report`追加とreport件数の改変、
追加環境変数、期待statusの改変、一時file残存の許容、report件数2件、explicit-reportからread-onlyへの変更、
read-only caseへのreport directory追加、verify commandの書込みcommandへの置換をいずれも拒否する。
Core、process runner、report writerは実装しない。実際の書込み有無はGate Bで受け入れる。

## SINGLE-125-06を保留する理由

matrixの条件は「reportの排他的作成失敗」「既存file不変、一時file残存0件」である。
fixture形式で固定できるのはfileとsymlinkの配置だけで、時刻の固定や障害注入はできない。
report名は生成時刻を含むため、既存fileとの名前衝突を決定論的に起こせない。
仕様上一意に失敗させられる入力は「`.spec/reports`の位置に通常fileがある」だけだが、これはSINGLE-072と同一になる。
発生条件の裁定後に、同じ変更で唯一の期待fileを追加する。
