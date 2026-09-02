# Core 1.0実装計画

- 状態: Active
- 作成日: 2026-09-01
- 前提: [ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)、
  [ADR-040](../02.設計書/10_決定記録/ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md)、
  [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)

## 1. 目的

規範設計と実装順序を分離し、workspace単独のEARS-AI記述からtest実行までの垂直スライスを先に実証した後、
同じ契約をモノレポ連合へ拡張する。
Phase番号と完了条件は計画であり、Core APIの規範ではない。

## 2. Phase 0: 実証条件

- 通常Markdownまたは従来EARSを使う比較taskを5件固定する。
- 完了時間、仕様記述時間、review時間、欠陥検出数を定義する。
- 単一workspaceと20 member連合の基準fixtureを固定する。
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

完了条件は、同名ローカルIDを持つmember、横断refinement、所有境界違反を決定論的に区別し、
`check --all-workspaces`と`verify --all-workspaces`が基準性能を満たすことである。別member所有bindingを1回だけ実行し、
request targetとowner memberのstatusへ反映してもcommand実体とdurationを複製しないことをfixtureで確認する。

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
