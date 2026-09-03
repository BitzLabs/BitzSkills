# Core 1.0実装計画

- 状態: Active
- 作成日: 2026-09-01
- 前提: [ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)、
  [ADR-040](../02.設計書/10_決定記録/ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md)、
  [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)、
  [ADR-042](../02.設計書/10_決定記録/ADR-042_モノレポ連合のidentity・所有境界・公開契約を確定する.md)、
  [ADR-043](../02.設計書/10_決定記録/ADR-043_モノレポ連合の継続・TASK境界・適合契約を確定する.md)

## 1. 目的

規範設計と実装順序を分離し、workspace単独のEARS-AI記述からtest実行までの垂直スライスを先に実証した後、
同じ契約をモノレポ連合へ拡張する。
Phase番号と完了条件は計画であり、Core APIの規範ではない。

## 2. Phase 0: 実証条件

- 通常Markdownまたは従来EARSを使う比較taskを5件固定する。
- 完了時間、仕様記述時間、review時間、欠陥検出数を定義する。
- 単一workspaceと、20 workspace、SPEC 1,000件、relation 20,000件の基準連合fixtureを固定する。
- 平均file byte、statement数、edge密度、横断Contextの到達workspace数と基準環境manifestを固定する。
- Core 1.0対象外機能を確認する。

完了条件は、比較方法と成功基準が実装前に固定されていることである。

## 3. Phase 1: EARS-AIと文書モデル

- 候補Scanner、Lexer、Parser、Semantic IR
- `bitz.yaml`とFrontmatter Schema
- 文書ID、statement ID、状態、関係索引
- 正例・反例fixture

完了条件は、同一入力から同一IRとDiagnosticを再現できることである。

## 4. Phase 2: Contextとcheck

- 強い依存の完全閉包
- Constraint Ledger、coverage、Context Digest
- `--expect-digest` stale検出
- changed-only check、`--full`、明示対象
- REQ保護、状態遷移、TASK境界
- relation Diagnosticの1 edge 1 primary規則
- TASK directory prefixの字句許可とbase/current canonical所有判定

完了条件は、参照切れ、循環、上限、Digest不一致を部分成功にせず、基準性能を満たすことである。

## 5. Phase 3: verifyとdoctor

- command名単位のbinding解決
- `{tests}`展開、cwd、timeout、出力上限
- target単位Context、`targetResults[]`、共有bindingの1回実行
- verify結果と明示`--report`時だけの最小report
- 導入、互換性、Git縮退、command診断

完了条件は、test成功、非0、起動失敗、signal、timeout、対象0件をfixtureで区別でき、異なる2 Contextを持つtarget、
共有binding、Context非成功targetの混在を正しい`targetResults[]`へ対応付けられることである。`--report`なしでは
成功・非成功とも既存reportを変更せず、新しいfileを作らないことを検証する。

## 6. Phase 4: モノレポ連合

- 明示catalog、active workspace、修飾ID
- 横断Frontmatter索引、完全Context、Context Digest
- code／test／TASK／cwdの所有境界
- `--workspace`と`--all-workspaces`
- workspace別`targetResults[]`、共有command結果、集約status、明示連合report
- 未登録member、path重複、Git不在、横断参照、対象0件fixture
- Git既知の未登録設定、symlink所有迂回、case差、初回root ID写像、member移動・削除fixture
- 連合Contextとcheck／verify／doctor全体結果の期待JSON
- byte、statement、edge、trace、command、bindingの上限直前・直後fixture
- 文書・target・binding単位の継続と`SPEC-MONOREPO-DEPENDENCY-001`
- 単一／連合dual-read consumer、原子的rollback、部分rollback拒否fixture

完了条件は、同名ローカルIDを持つmember、横断refinement、所有境界違反を決定論的に区別し、
`check --all-workspaces`と`verify --all-workspaces`が基準性能を満たすことである。別member所有bindingを1回だけ実行し、
request targetとowner memberのstatusへ反映してもcommand実体とdurationを複製しないことをfixtureで確認する。

性能はCore cacheを使わず、暖機1回後の5回中央値で測定する。基準環境で`check --all-workspaces`を30秒以内、
3 workspaceへ到達する20文書・128 KiB以下のContextを1秒以内、Core peak RSS増分を200 MiB以内とする。
10,000 SPEC fixtureは性能SLOではなくhard limitの安全停止を検証する。索引memoryは入力graph size、target一時memoryは
最大Context閉包へ線形とし、全targetの完全Bundleを同時保持しない。resource dimensionごとに`limit - 1`、`limit`、
`limit + 1`を分離し、最大dimension fixtureをCore peak RSS増分1 GiB以下、2 GiB memory limit下で正常終了させる。

適合fixtureは`fixtures/conformance/monorepo/<fixture-id>/`へ入力repository、manifest、期待JSONを置く。manifestは
実行directory、argv、Git base/current、期待終了コード、report条件を持つ。共通normalizerは`durationMs`、生成時刻、
環境依存process出力だけを除外し、fixture固有の除外fieldを許さない。最低限、同名local ID、横断refinement、
Diagnostic優先順位、未登録設定、symlink、TASK prefix、独立継続、multi-context verify、共有binding、0件、identity、
Git不在、resource境界、report副作用、consumer、rollbackを期待status／code／配列順まで構造比較する。fixture ID、
status、終了コード、必須確認の最小matrixは[提案23 §8](23_モノレポ残存P2裁定案.md#8-f-適合fixtureと期待matrix)を使う。

## 7. Phase 5: SDD垂直スライス

REQ 1件について次を通す。

```text
SPEC作成 -> context -> pre-check -> code/test変更 -> post-check -> verify -> human review
```

通常Markdown条件と比較し、完了時間、欠陥率、review負荷のいずれも改善しない機能を既定経路へ追加しない。

## 8. 1.0以降の再評価候補

- ID改番支援
- 実Profile
- Projection Digest
- formatter／style linter
- より細粒度のtest selector

候補は提案11の再評価条件を満たした場合だけ新しいADRから開始する。
