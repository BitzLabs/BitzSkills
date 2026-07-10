---
description: |
  ポジショニング（Dunford 5コンポーネントキャンバス）、タッチポイント × デバイス × タイミングのマトリックス、および動機付け/維持のループ（Fogg + Hook + Kano delighter refresh）を1つのドキュメントで設計します。機能ではなく顧客価値を主張し、ダークパターンを避けます。/product:design-positioning [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Positioning & Engagement

## Desired Outcome

1つの成果物を作成します：

1. **ポジショニング（Positioning）** — `reports/01_ux/positioning.md`（`POS-` および `HOOK-` IDs）:
   1. **ポジショニングキャンバス（Dunford 5）（Positioning canvas (Dunford 5)）** — 競合する代替品、独自の属性、価値（+証拠）、ターゲットセグメント、市場カテゴリ
   2. **差別化 vs パリティ（Differentiation vs parity）** — 選択された PoD vs PoP（市場ランドスケープから）
   3. **タッチポイント × デバイス × タイミングマトリックス（Touchpoint × device × timing matrix）** — ジャーニータッチポイントごとの、デバイスとメッセージが配信されるタイミング
   4. **フックキャンバス（Hook canvas）**（`HOOK-`） — トリガー（Trigger） → アクション（Action） → 変動する報酬（Variable Reward） → 投資（Investment）
   5. **狩野モデルの魅力的品質（delighter）リフレッシュ計画（Kano delighter refresh plan）** — 魅力的品質が当たり前品質へと陳腐化するにつれて、差別化がどのように継続的に補充されるか

## Invocation

```
/product:design-positioning [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしで上流の成果物から生成します。ギャップは `TBD` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **機能ではなく、価値（顧客の成果）を主張する。** ポジショニングは Dunford の順序（代替品 → 属性 → 価値 → セグメント → カテゴリ）を介して意図的に導き出されます。
- **パリティ（同等性）で戦わない。** 防御可能な少数の PoD（Point of Difference: 差別化ポイント）に集中します。魅力的品質は陳腐化することを前提とし、リフレッシュを計画します。
- **維持（Retention）は指標を動かさなければならない。** 各フック/エンゲージメントの戦術は、`NSM-` の維持/エンゲージメント入力指標を前進させる必要があります。
- **ダークパターンなし。** エンゲージメントは価値を通じて獲得されるものであり、決して強制や欺瞞的なUXによるものではありません。
- **終了条件（Stop condition）**: 5コンポーネントのポジショニングキャンバス、タッチポイント×デバイス×タイミングマトリックス、`NSM-` に結び付けられたフックキャンバス、および魅力的品質のリフレッシュ計画が存在すること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/01_ux/journey-maps.md` | Required | `/product:map-journey` | メッセージを出してブロックする — マトリックスにはタッチポイントが必要です |
| `reports/00_core/market-landscape.md` | Optional | `/product:research-landscape` | PoD/PoP をインラインで導出するか、`TBD` とマークします |
| `reports/00_core/success-metrics.md` | Recommended | `/product:define-success-metrics` | フック戦術に `NSM-` アンカーが不足しています。`TBD` とマークします |
| `reports/00_core/vision-mission-value.md` | Required | `/product:define-vision` | メッセージを出してブロックする |

## Process

1. **コンテキストの読み取り** — ジャーニーマップ、市場ランドスケープ、サクセスメトリクス、ビジョン、`work/traceability.json`。
2. **ポジショニングのフレーミング（Frame positioning）** — Dunford の順序による、カテゴリ → 価値 → 独自の属性。`@rules/product/positioning-kano-hook.md` を適用します。
3. **マトリックスの構築（Build the matrix）** — 各ジャーニータッチポイントにデバイス + タイミングを割り当てます。
4. **エンゲージメントの設計（Design engagement）** — Fogg（動機 × 能力 × プロンプト）による動機付け。投資ステップが切り替えコスト（switching cost）を蓄積するフックループによる維持。
5. **リフレッシュ計画（Refresh plan）** — 狩野モデルの魅力的品質（delighters）の補充をスケジュールします。
6. **トレーサビリティの追記** — 上流の `JNY-`/`NSM-`/市場 参照を持つ `POS-`/`HOOK-` ノードを `work/traceability.json` に追加します。
7. **記録** — ファイルを書き込みます。決定事項を `work/context.md` に追記します。`TBD` をログに記録します。

## Output

`reports/01_ux/positioning.md`、`POS-`/`HOOK-` ID テーブル（Upstream 列を含む）、タッチポイントマトリックス、および魅力的品質のリフレッシュ計画が含まれます。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/positioning-kano-hook.md` | Dunford キャンバス、PoD/PoP、狩野モデル（Kano）、Fogg + Hook、タッチポイントマトリックス |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:map-journey` | Upstream — タッチポイントはマトリックスに供給されます |
| `/product:research-landscape` | Upstream (optional) — PoD/PoP と狩野モデルのソース |
| `/product:define-success-metrics` | Upstream — フック戦術は `NSM-` 指標をターゲットにします |
| `/product:generate-ui-mock` | Downstream — ポジショニングはモックに情報を提供します |
| `/product:adapt-change` | 競争の枠組みが変わったときにこの Skill を再実行します |
