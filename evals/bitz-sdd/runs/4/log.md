# Run 4
- **ケース**: TC-03
- **モード**: スキルあり（エッジケース）
- **実行日時**: 2026-07-11 04:05

## 手順の記録

1. `sdd-core` の SKILL.md フェーズ・ルーティング表を確認。「データ格納設計（永続データを扱う場合のみ）→ `sdd-data`」との記載があり、必須工程ではないことを確認。
2. `sdd-data` の SKILL.md description を確認：「データを永続化しないシステムでは不要（必須工程ではない）」と明記。また本文冒頭にも「データを永続化しないシステムではこの工程をスキップしてください（必須ステップではない）」と重ねて明記されている。
3. **sdd-data スキップの判断根拠**: 入力プロンプトは「電卓CLIツール（履歴保存なし・完全ステートレス）」であり、計算結果や入力式を一切保存しない。ユーザー要求そのものが「非永続」を明示しているため、sdd-data の適用条件（永続データを扱う場合のみ）に該当しない。したがって sdd-core のフェーズ表と sdd-data の description の両方に従い、**sdd-data を明示的にスキップする**と判断した。
4. `sdd-design` の SKILL.md に従い、bitz-ddd 未導入前提の軽量ドメインスケッチとして `.spec/design/domain-model.md`（DSN-001）を作成。ただしステートレスな性質上、エンティティではなく Expression / CalculationResult という値オブジェクト中心の最小限記述とした。
5. `.spec/design/architecture.md`（DSN-002）に論理ビュー（Parser→Evaluator→Output の3ステップ、Mermaid flowchart）、プロセスビュー、配置ビュー、技術適合性評価を最小限で作成。データ層は「存在しない」旨を明記。
6. `sdd-review` の SKILL.md と `review-registry.json` を確認。`data-integrity` 観点は `conditions: persistent-data` と定義されており、永続データを扱わない本ケースでは同観点が自動的に対象外となることをレジストリの条件定義から確認。`.spec/reviews/review-synthesis.md`（REV-001, decision: PASS）にその旨を明記し、残り4観点（consistency/operations/risk/business）で判定。
7. 指示どおり `sdd-data` は使用せず、`data-model.md` は作成していない。sdd-report / sdd-docs の実行は本ケースの依頼範囲外のため実施していない（指示に「design（domain-model / architecture の最小限）→ review の流れだけ回し」とあるため）。

## 成果物

`evals/bitz-sdd/runs/4/calc-cli/.spec/` 配下に以下をコピー保存:
- `design/domain-model.md`（DSN-001）
- `design/architecture.md`（DSN-002）
- `reviews/review-synthesis.md`（REV-001, PASS）

`data-model.md` は意図的に作成していない（スキップの判断根拠は上記手順3参照）。

## 備考

- sdd-data のスキップ判断は、sdd-core のフェーズ表（「永続データを扱う場合のみ」）と sdd-data 自身の description・本文冒頭（二重に明記された非必須の宣言）の2箇所から一貫して導出でき、判断に迷いはなかった。
- レビューの `data-integrity` 観点が `conditions: persistent-data` という条件付きで定義されていたため、sdd-data スキップとレビュー観点の除外が構造的に整合していることを確認できた（レジストリの設計がスキップ判断を後段でも裏付ける形になっている）。
- 本ケースはエッジケースとして「必須工程を空気を読まず機械的に実施してしまわないか」を見る狙いだと理解し、過剰倹約（ドメインモデル自体を省略する等）はせず、スコープに応じた最小限の記述に留めた。
