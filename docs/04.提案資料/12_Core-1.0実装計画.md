# Core 1.0実装計画

- 状態: Active
- 作成日: 2026-09-01
- 更新日: 2026-09-11
- 前提: [ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)、
  [ADR-040](../02.設計書/10_決定記録/ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md)、
  [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)、
  [ADR-042](../02.設計書/10_決定記録/ADR-042_モノレポ連合のidentity・所有境界・公開契約を確定する.md)、
  [ADR-043](../02.設計書/10_決定記録/ADR-043_モノレポ連合の継続・TASK境界・適合契約を確定する.md)、
  [ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)、
  [ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md)

## 1. 目的

規範設計と実装順序を分離し、公開面の配管を先に通したうえで、workspace単独のEARS-AI記述から
test実行までの垂直スライスを実証し、同じ契約をモノレポ連合へ拡張する。
Step番号と完了条件は計画であり、Core APIの規範ではない。

適合条件の正本は[適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、
Digestの計算手順は[Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md)である。
本書はそれらを再定義せず、実装順序と各Stepの完了条件だけを持つ。

### 1.1 進行状態とGate

Stepの進捗、次工程への許可、受入結果を混同しないため、次の語彙を使う。

| 対象 | 状態語彙 | 意味 |
|---|---|---|
| Step | `Not started` / `In progress` / `Complete` | 作業そのものの進捗 |
| Gate A | `Blocked` / `Allowed` | Step 1へ進むことの可否 |
| Gate B / Gate C | `Pending` / `Passed` / `Failed` | 固定した検査に対する受入結果 |

Core 1.0のGateは次の3層とする。

| Gate | 判定時点 | 判定対象 | 現在状態 |
|---|---|---|---|
| Gate A: 実装着手可能性 | Step 1開始前 | 規範、fixture、期待値、検証基盤がCore実行体なしで再現可能 | `Blocked` |
| Gate B: Step別実装受入 | 各Step完了時 | 当該StepのCore実装が固定済みfixtureへ適合 | `Pending` |
| Gate C: Core 1.0リリース受入 | 全Step完了後 | 全適合、性能、自己適用を含む出荷可能性 | `Pending` |

Gate条件の正本は本書、fixture構造と比較方法の正本は
[適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md)とする。提案資料は判断理由と移行履歴、
提案資料READMEは現在状態の要約だけを持つ。

## 2. Step 0: 仕様確定（コードを書かない）

状態は`Complete`である。成果物は次とし、いずれも[提案24](24_Core-1.0実装着手方針.md)の裁定に対応する。
Step 0完了はGate Aの必要条件だが、それだけでStep 1の開始を許可しない。

| 成果物 | 対象 | 状態 |
|---|---|---|
| [Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md) | G1 | 反映済み |
| [適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md) | G2 | 反映済み |
| Diagnostic表の閉包（共通契約 §6.1と各操作仕様） | G3 | 反映済み |
| 終了コード4の出力契約（共通契約 §3） | G4 | 反映済み |
| [ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md) | G5 | 反映済み |
| 非成功時のtext出力契約（共通契約 §7） | G6 | 反映済み |
| [Core実行環境・CLI基盤契約](../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md) | G7 | 反映済み。判断理由はADR-045 |
| accepted ADRのlink訂正とcheck status語彙の所有 | G8 | 反映済み |

完了条件は、G1〜G8が規範文書だけを読んで一意に実装できることである。

## 3. Step 0-P: 実証条件

状態は`Complete`である。入力形状、対象外機能、比較方法、成功基準を固定し、
`uv run fixtures/validate_step0p.py`でSchema検証と2回生成一致を確認した。
検証記録は[Step 0-P検証結果](../../fixtures/step0p-validation.md)を参照する。

入力、generator、期待digest、reference environment、測定protocol、比較task、成功基準はStep 1開始前に固定する。
Core実行結果と人間による比較結果は、それぞれの対象機能が実装された後に取得する。

- 通常Markdownまたは従来EARSを使う比較taskを5件固定する。
- 完了時間、仕様記述時間、review時間、欠陥検出数を定義する。
- 単一workspaceと、20 workspace、SPEC 1,000件、relation 20,000件の基準連合fixtureを固定する。
- 平均file byte、statement数、edge密度、横断Contextの到達workspace数と基準環境manifestを固定する。
- Core 1.0対象外機能を確認する。

完了条件は、比較方法と成功基準が実装前に固定されていることである。

成果物の正本は[`fixtures/performance`](../../fixtures/performance/README.md)と
[`fixtures/comparison`](../../fixtures/comparison/README.md)である。基準treeはversion管理したmanifestとgeneratorから再生成し、
件数と期待tree digestが一致しなければ測定を開始しない。

### 3.1 Step 0B: Gate A実証基盤

状態は`In progress`、Gate Aは`Blocked`である。Step 0で確定した契約を機械検証可能な入力、期待値、
generator、helper、harnessへ落とし込み、fresh checkoutから再現できることを示す。

部分検証の入口は`uv run fixtures/validate_step0b.py`。公開JSON、grammar参照、link、Git setup、process helper、
副作用比較の自己試験、Step 0-P、Diagnostic意味網羅の対応台帳検証、target期待集合25ケースを統合済みである。
適合fixture 311件中、導入・設定9件、EARS-AI構文・候補抽出・拡張12件、文書構造・UTF-8 9件、関係・path・coverage 6件は入力・期待JSON・副作用期待値を作成し、隔離setupの2回一致を検証した。
残275件の適合fixture、golden Context Digest、残fixtureの副作用期待値は未完了であり、全Gate A検証の完了は宣言しない。

このStepで実装してよいのはSchema検証、fixture generator、reference計算、grammar検査、matrix検査、
process用test helper、副作用比較harness、独立cross-checkである。`doctor`、`context`、`check`、`verify`、
本番Parser、target展開、Digest生成、process runnerの公開挙動を実装してはならない。

Gate Aを`Allowed`にする条件は次の全件である。

- P0 6件が規範文書へ反映されている
- 公開JSON例がmachine-readable Schemaを全件通過する
- 規範上の全非成功条件がDiagnostic registryへ対応する
- grammarに未定義tokenまたはnonterminalがない
- target種別とpurposeの全組合せに対する期待集合fixtureが存在する
- fixture matrixに選択的期待、複数原因、`元status`がない
- Gitのbase、current、staged、worktree、unbornをmanifestから再現できる
- 単一と連合のCanonical JSONおよびgolden Context Digestが独立した2系統のreference計算で一致する
- read-only、report、cacheの変更前後snapshotと許可書込みが固定され、副作用比較harness自体を自己検査できる
- timeout、signal、子process、pipe保持を再現するhelperと有限時間で失敗できるharnessが存在する
- 性能基準fixture、決定論的generator、期待tree digest、reference environmentがversion管理されている
- 現行正本とaccepted ADRの相対link検査が0件である
- 上記をCore実行体へ依存しない単一commandでfresh checkoutから再実行でき、2回の結果が一致する

全条件を通過した自動検査結果と実行環境を同一commitへ記録した時点でStep 0Bを`Complete`、Gate Aを
`Allowed`とし、Step 1の開始を許可する。Core本体と期待値の一致はGate Aに含めず、該当するGate Bで判定する。

## 4. Step 1: 骨格と`doctor`

`doctor`は設定読込み、workspace発見、結果・Diagnostic・終了コードの配管だけで成立する最小の操作であり、
他3操作が同じ土台を使う。ここを先に通し、以後の全Stepを同じ公開面から検証する。

- 適合fixture harness: manifest実行、共通normalizer、副作用比較、終了コード判定
- CLI引数解析、`--format`、終了コード0〜4、引数不正時の標準エラー1行
- 共通結果外形、Diagnostic Schema、source、順序規則、status集約
- text出力の要約行とDiagnostic行
- `bitz.yaml`のYAML subset読込みと禁止構文の拒否
- 単一workspaceの探索と`doctor`（Core、実行環境version、設定、Git、command）

完了条件は、`SINGLE-001`〜`006`、`SINGLE-070`〜`078`、`SINGLE-081`、`083`、`091`〜`095`、
`SINGLE-104`〜`106`、`125-02`、`127-01`〜`02`、`127-05`〜`07`、`127-11`、`127-14`〜`19`が通過し、
終了コード0〜4を区別できることである。

## 5. Step 2: EARS-AIと文書モデル

- 候補Scanner、Lexer、Parser、Semantic IR
- Frontmatter Schema、文書ID、statement ID、状態、file名規則
- 関係索引、逆索引、path逆索引
- 正例・反例fixture

完了条件は、同一入力から同一IRとDiagnosticを再現でき、`SINGLE-007`〜`026`、`SINGLE-079`〜`080`、
`SINGLE-082`、`084`〜`090`、`096`〜`103`、`114`〜`120`が通過することである。

## 6. Step 3: Contextとcheck

- 強い依存の完全閉包、purpose別閉包、role分類
- Constraint Ledger、coverage、Context Digest
- `--expect-digest` stale検出、detailとexpandのprojection
- changed-only check、`--full`、明示対象、Git基準版
- REQ保護、状態遷移、管理済みSPEC削除、TASK境界、影響候補
- relation Diagnosticの1 edge 1 primary規則

完了条件は、参照切れ、循環、上限、Digest不一致を部分成功にせず、`SINGLE-027`〜`054`が通過し、
`SINGLE-107`〜`112`、`121`〜`124`、`125-01`、`125-03`、`125-05`〜`06`、`127-03`〜`04`、
`127-12`〜`13`が通過し、`SINGLE-042`の
Canonical JSONとDigestが規定値にbyte一致することである。

## 7. Step 4: verify

- command名単位のbinding解決、`{tests}`展開、cwd、timeout、出力上限
- target単位Context、`targetResults[]`、共有bindingの1回実行
- verify結果と明示`--report`時だけの最小report

完了条件は、test成功、非0、起動失敗、signal、timeout、対象0件をfixtureで区別でき、異なる2 Contextを持つtarget、
共有binding、Context非成功targetの混在を正しい`targetResults[]`へ対応付けられることである。`--report`なしでは
成功・非成功とも既存reportを変更せず、新しいfileを作らない。`SINGLE-055`〜`069`、`SINGLE-107`〜`108`、
`110`、`112`〜`113`、`125-04`、`126`、`127-08`〜`10`が通過する。timeout fixtureは子孫がpipeを保持してもtimeout到達から
5秒以内に結果を確定し、計画済みの独立bindingを継続する。

## 8. Step 5: モノレポ連合

- 明示catalog、active workspace、修飾ID
- 横断Frontmatter索引、完全Context、Context Digest
- code／test／TASK／cwdの所有境界とcanonical path判定
- `--workspace`と`--all-workspaces`
- workspace別`targetResults[]`、共有command結果、集約status、明示連合report
- 未登録member、path重複、Git不在、横断参照、対象0件
- Git既知の未登録設定、symlink所有迂回、case差、初回root ID写像、member移動・削除
- 文書・target・binding単位の継続と`SPEC-MONOREPO-DEPENDENCY-001`
- 単一／連合dual-read consumer、原子的rollback、部分rollback拒否

完了条件は、同名ローカルIDを持つmember、横断refinement、所有境界違反を決定論的に区別し、
`check --all-workspaces`と`verify --all-workspaces`が基準性能を満たし、`MONO-001`〜`025`が通過することである。
`MONO-002-01`のCanonical JSONとDigestが連合golden値にbyte一致し、2回実行でも変化しないことを含む。
別member所有bindingを1回だけ実行し、request targetとowner memberのstatusへ反映してもcommand実体とdurationを
複製しない。

## 9. Step 6: SDD垂直スライスと自己適用

Step 2完了時点でbitz-core自身の`.spec/`を作り、以後の実装をSmall Flowで進める。
最初のREQはParserと結果契約に対するものとし、Coreが自分自身をcheck・verifyできる状態をStep 4の完了条件へ含める。

その上でREQ 1件について次を通す。

```text
SPEC作成 -> context -> pre-check -> code/test変更 -> post-check -> verify -> human review
```

通常Markdown条件と比較し、完了時間、欠陥率、review負荷のいずれも改善しない機能を既定経路へ追加しない。

### 9.1 Gate C: Core 1.0リリース受入

全StepのGate Bが`Passed`した後、次を全件満たした場合だけGate Cを`Passed`とする。

- 全conformance fixtureが通過する
- 性能baselineを基準環境で取得し、§10のSLOを満たす
- 単一と連合のCanonical JSONおよびContext Digestが2回実行でbyte一致する
- read-only、report、cache、timeout、signal、子processの受入試験が通過する
- bitz-core自身の`.spec/`でSmall Flowを完走する
- 通常Markdown条件との完了時間、欠陥率、review負荷の比較結果を記録する
- 未解決のP0またはP1がない

## 10. 性能受入

性能はCoreの永続cacheなしで、OS file cacheの暖機1回後の5回中央値を測定する。基準環境で`check --all-workspaces`を30秒以内、
3 workspaceへ到達する20文書・128 KiB以下のContextを1秒以内、Core peak RSS増分を200 MiB以内とする。
10,000 SPEC fixtureは性能SLOではなくhard limitの安全停止を検証する。索引memoryは入力graph size、target一時memoryは
最大Context閉包へ線形とし、全targetの完全Bundleを同時保持しない。resource dimensionごとに`limit - 1`、`limit`、
`limit + 1`を分離し、最大dimension fixtureをCore peak RSS増分1 GiB以下、2 GiB memory limit下で正常終了させる。

測定条件と性能fixtureの位置づけは
[適合fixture仕様 §8](../03.詳細設計/00_共通契約/04_適合fixture仕様.md#8-性能fixture)に従う。
性能fixtureは合否matrixへ含めず、回帰検査として独立に運用する。

## 11. 1.0以降の再評価候補

- ID改番支援
- 実Profile
- Projection Digest
- formatter／style linter
- より細粒度のtest selector
- MCP面（[ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)）

候補は提案11の再評価条件を満たした場合だけ新しいADRから開始する。
