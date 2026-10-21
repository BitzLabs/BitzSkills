---
id: ADR-066
title: 単独のverifyの上限を実行計画の確定後に判定する
status: accepted
relations:
  related:
    - ADR-063
---

# ADR-066 単独のverifyの上限を実行計画の確定後に判定する

## Context

[複合ワークスペース仕様](../../03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md) §10は、`verify`では`commandDefinitionCount`の判定を
実行計画を確定した後に行い、`verifyBindingCount`も超過していれば`verifyBindingCount`を優先して報告すると定める。`verify --all-workspaces`はこのとおりに動く。

一方、[ADR-063](ADR-063_複合ワークスペースの単独操作の全体事前検査を確定する.md)の`Decision`の8番目の項目は、単独の`verify`の全体事前検査が
`commandDefinitionCount`を含むすべての次元を判定するとし、単独の`verify`が`verifyBindingCount`と次元の優先を判定しない点を別の欠陥とした（実装の確認事項C40）。
このため、単独の`verify`では、両方の次元が超過しても`commandDefinitionCount`を報告し、§10の優先に反していた。

## Decision

1. **部分改訂**。本ADRは、ADR-063の`Decision`の8番目の項目を、次の2.のとおり部分改訂する。ADR-063のほかの`Decision`は変えない。
2. **単独の`verify`**。複合ワークスペースの単独の`verify`は、`--all-workspaces`と同じく、`commandDefinitionCount`を全体事前検査では判定せず、
   実行計画を確定した後（対象展開とテスト割当ての重複排除が終わった後、コマンドを1件も起動する前）に、`verifyBindingCount`と合わせて判定する。
   両方が超過していれば`verifyBindingCount`、`commandDefinitionCount`だけが超過していればそれを、診断`SPEC-MULTI-LIMIT-001`（`blocked`）で報告する（ユーザーの決定）。
   `verifyBindingCount`は1回の実行計画にあるテスト割当ての数、`commandDefinitionCount`は全ワークスペースのコマンド定義数とする（§10の表）。
3. **優先の範囲**。§10の「複数の次元が同時に超過する場合は、`verify`実行計画の次元を優先して報告する」は、`commandDefinitionCount`と`verifyBindingCount`の
   組に当てる。ほかの次元は、今どおり全体事前検査で判定する（司令塔の判断をユーザーに伝えた。§10に明記）。

## Consequences

- 単独の`verify`と`verify --all-workspaces`で、上限の判定の時期と優先がそろう。
- `commandDefinitionCount`だけが超過し、`--workspace`のIDがカタログにない場合は、全体事前検査が成功するため、引数不正（終了コード4）になる
  （以前は全体事前検査の停止で`blocked`／2）。ADR-063の決定3（全体事前検査が非成功なら終了コード4より診断を優先する）は、全体事前検査が成功した場合には当てはまらない。
- 実行計画の確定後の停止は全体事前検査の停止ではないため、`--workspace`または修飾IDで別のワークスペースを作業ワークスペースにした場合、停止結果の`workspace`と
  `--report`の保存先は作業ワークスペースのものになる（以前は全体事前検査の停止として、現在のディレクトリから選んだ設定のもの）。
- `commandDefinitionCount`の`evidence`の`observedAtLeast`は、全ワークスペースのコマンド定義数の総数になる（以前は全体事前検査の早期停止の累計。
  §10の「早期に停止したときの`observedAtLeast`」の範囲内で、`--all-workspaces`と同じ値）。
- この扱いを固定する適合fixtureを追加する（ADR-051の追加）。既存のfixtureの入力と期待値は変えない。

## Alternatives

1. **`commandDefinitionCount`だけで止まったときに限り判定を遅らせる**: 既存の挙動を最も変えないが、判定の時期が入力で分かれる。採らない（ユーザーの決定）。
2. **優先の規則を`--all-workspaces`に限ると仕様に書く**: Coreは変えずに済むが、単独と全体で上限の報告が分かれる。採らない（ユーザーの決定）。

## Notes

- 実装の確認事項C40の解決である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-10-22 | 単独の`verify`の`commandDefinitionCount`を実行計画の確定後に判定することを起案・採用し、ADR-063のDecision 8を部分改訂 | 実装の確認事項C40 |
| 2026-10-22 | 独立レビューの指摘で、停止結果の`workspace`と`observedAtLeast`の変化をConsequencesに書き、優先の範囲を§10に明記（判断は変えない） | 実装の確認事項C40 |
