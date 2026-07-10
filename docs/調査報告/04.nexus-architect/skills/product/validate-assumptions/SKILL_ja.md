---
description: |
  戦略が依存する最もリスクの高い仮定を抽出し、それぞれに最も安価なテストと、中止/ピボット（kill/pivot）のしきい値を付加して、Go/No-Go（進行/中止）の判定を返します。ドキュメント生成と仮説検証を結びつける検証ゲート（validation gate）です。
  /product:validate-assumptions [--auto] [--lang=ja|en]。証拠が集まるにつれて再実行可能です。
model: opus
user_invocable: true
---

# Validate Assumptions (Gate)

## Desired Outcome

2つの成果物と、ゲートの判定を作成します：

1. **仮定（Assumptions）** — `reports/00_core/assumptions.md`（`ASM-` IDs）: 各反証可能な仮定を、**望ましさ（desirability）**（彼らはそれを欲しがるか） / **実現可能性 / 事業性（viability）**（それはお金を生むか） / **実現可能性 / 技術性（feasibility）**（我々はそれを構築できるか）に分類し、崩壊時の影響（「もしこれが間違っていたら、戦略のどれくらいが崩壊するか？」）によってランク付けします。
2. **検証計画（Validation plan）** — `reports/00_core/validation-plan.md`: 各上位 `ASM-` について、最も安価なテスト（顧客インタビュー、スモークテスト / フェイクドア ランディングページ、コンシェルジュ MVP、オズの魔法使い、**プレセール** — 最も強力な事業性テスト）、**中止/ピボットのしきい値（kill/pivot threshold）**、および現在のステータス。
3. **ゲート判定（Gate verdict）** — `work/pipeline-progress.json` → `gates.validate-assumptions` に書き込まれます: 未解決の（未テストで、高リスクの）仮定のリストを伴う `go` または `no-go`。

## Invocation

```
/product:validate-assumptions [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしで生成します。ギャップは `TBD` として記録します |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **何が戦略を反証するかを名指しする。** この Skill は、各上位の仮定に反証可能なステートメント、最も安価なテスト、および中止/ピボットのしきい値が備わるまでは完了しません。
- **価格と CAC は仮定であり、算術ではありません。** ビジョン/スコープ/収益の作業から `TBD-assumption` の値を引き出し、それらを計算すべき数値としてではなく、市場で検証すべき項目（例: Van Westendorp、プレセール）として扱います。
- **判定ロジック（Verdict logic）**: 崩壊の致命的な仮定が未テストであり、かつ定義されたテスト+しきい値が欠けている場合は `no-go`。それ以外の場合は `go`（追跡のために未解決の仮定をリストアップします）。
- **終了条件（Stop condition）**: 上位の仮定がランク付けされ、それぞれにテスト+しきい値が設定され、判定が記録されていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/00_core/vision-mission-value.md` | Required | `/product:define-vision` | メッセージを出してブロックする |
| `reports/00_core/scope-definition.md` | Required | `/product:define-scope` | メッセージを出してブロックする |
| `reports/00_core/success-metrics.md` | Optional | `/product:define-success-metrics` | 存在する場合は使用します |
| `reports/00_core/revenue-model.md` | Optional | `/product:design-revenue` | 存在する場合は、価格/CAC の仮定を引き出します |

## Process

1. Phase 1 のすべての成果物と `work/traceability.json` を**読む（Read）**。
2. **抽出（Extract）** — すべての反証可能な仮定を抽出します（需要、価格、CAC、チャネル、主要な技術的リスクに焦点を当てます）。望ましさ / 事業性 / 技術的実現可能性（desirability / viability / feasibility）を分類します。
3. **ランク付け（Rank）** — 崩壊時の影響によってランク付けします（最もリスクの高い仮定からテストする（Riskiest-Assumption-Test）マインドセットを使用します: 最も危険な信念を最初に）。
4. **計画（Plan）** — 各上位の仮定に対して、最も安価で信頼できるテストと、中止/ピボットのしきい値を割り当てます。`@rules/product/assumption-validation.md` を適用します。
5. **判定（Verdict）** — `go` / `no-go` を計算します。それ（および `open_assumptions`）を `pipeline-progress.json` → `gates` に書き込みます。
6. **トレーサビリティの追記** — 上流の `VIS-`/`SCP-`/`NSM-`/revenue 参照を持つ `ASM-` ノードを `work/traceability.json` に追加します（これにより、`adapt-change` はゲートを再び開くことができます）。
7. **記録** — 両方のファイルを書き込みます。判定を `work/context.md` に追記します。

## Rerun

証拠が集まるにつれて再実行し、各仮定のステータスと判定を更新します。ゲートは一度だけ実行するものではなく、再検討されることを意図しています。

## Output

`reports/00_core/assumptions.md` と `reports/00_core/validation-plan.md`、および `work/pipeline-progress.json` 内のゲート判定。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/assumption-validation.md` | 最もリスクの高い仮定のテスト、テストカタログ、Van Westendorp、Go/No-Go |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-vision` | Upstream — Go/No-Go の基準はここから発生します |
| `/product:define-scope` | Upstream — スコープの仮定はここで検証されます |
| `/product:start` | パイプラインをゲートするために判定を読み取ります |
| `/product:adapt-change` | 外部からの変更が仮定を無効にしたときにゲートを再び開きます |
