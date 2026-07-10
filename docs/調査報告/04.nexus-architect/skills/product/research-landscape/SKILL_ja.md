---
description: |
  市場と競合他社を1回のパスで調査します — 市場規模（TAM/SAM/SOM）、トレンド、代替案、競合マトリックス、および狩野分類（Kano classification） — その後、差別化（PoD）vs パリティ（PoP）戦略を推奨します。情報源は常に引用されます（名前 + URL）。
  /product:research-landscape [target] [--input=<file|dir>] [--auto] [--lang=ja|en] [--no-research]。
model: opus
user_invocable: true
---

# Market & Competitive Landscape

## Desired Outcome

1つの成果物を作成します：

1. **市場ランドスケープ（Market landscape）** — `reports/00_core/market-landscape.md`:
   - **市場の概要（Market overview）** — TAM/SAM/SOM（ボトムアップが望ましい）、トレンド、および現状維持/「何もしない」を含む代替案
   - **競合マトリックス（Competitive matrix）** — セグメントが関心を持つ次元における直接的・間接的な競合他社
   - **狩野分類（Kano classification）** — 当たり前品質（Must-be）（→ PoP / パリティ）vs 魅力的品質（Delighter）（→ PoD / 差別化）
   - **戦略の推奨（Strategy recommendation）** — PoP については効率的にパリティ（同等性）に到達し、防御可能な少数の PoD に集中します。魅力的品質は陳腐化し、リフレッシュが必要になることにフラグを立てます

すべての数値、競合他社、および主張には、情報源（名前 + URL）が付加されます。このファイルは `define-vision`、`design-revenue`、および `design-positioning` によって消費されます。

## Invocation

```
/product:research-landscape [target] [--input=<file|dir>]... [--auto] [--lang=ja|en] [--no-research]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `target` | Optional | プロダクト名 / 1行のアイデア（多くの場合、内部の呼び出し元から渡されます） |
| `--input=<file\|dir>` | Optional, repeatable | 既存の市場/競合資料 |
| `--auto` | Optional | ファシリテーションをスキップします。入力/調査からのみ統合します |
| `--lang` | Optional | 出力言語を上書きします |
| `--no-research` | Optional | `--input`/既存のドキュメントのみを使用します。ウェブを検索しません |

## Decision Criteria

- **情報源がない場合は、数値もなし。** 情報源のない市場規模や競合の主張は省略し、`TBD` としてログに記録します。効果を狙って推測することは決してしません。
- サイズ設定については**トップダウンよりもボトムアップ**（顧客数 × 価格 × 頻度 は「大きな数字のX%」に勝ります）。
- **パリティに過剰投資しない。** PoP における効率性と、PoD（魅力的品質）への集中を推奨します。
- **`--no-research`** は提供された資料に制限します。ギャップは `TBD` になります。
- **終了条件（Stop condition）**: 市場の概要、競合マトリックス、狩野モデルの分割、および PoD/PoP の推奨が存在し、それぞれが引用された情報源に裏付けられているか、`TBD` とマークされていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| プロダクトのアイデア / `target` / `--input` | Recommended | ユーザー または 内部の呼び出し元 | 既知の情報で進めます。ギャップには `TBD` とマークします |
| `reports/00_core/vision-mission-value.md` | Optional | `/product:define-vision`（これの前に実行される場合があります） | 進行します。この Skill は多くの場合、最初に実行されます |

## Process

1. **コンテキストの読み取り** — `target`、`--input`、`work/context.md`、存在する場合はビジョン。
2. **市場のサイズ設定（Size the market）** — ボトムアップによる TAM/SAM/SOM。情報源を記録します。
3. **調査（Research）**（`--no-research` を除く） — トレンド、代替案、競合他社。すべての事実について名前 + URL を引用します。
4. **比較（Compare）** — セグメントに関連する次元で競合マトリックスを構築します。ホワイトスペース（空白地帯）を特定します。
5. **分類と推奨（Classify & recommend）** — 狩野モデル（当たり前品質→PoP、魅力的品質→PoD）。差別化戦略を推奨します。`@rules/product/positioning-kano-hook.md` と `@rules/product/revenue-models.md` を適用します。
6. **トレーサビリティの追記** — 重要な発見事項（key findings）のノードを `work/traceability.json` に追加します。
7. **記録** — ファイルを書き込みます。決定事項を `work/context.md` に追記します。`TBD` を未解決の質問（Open Questions）にログとして記録します。

## Output

`reports/00_core/market-landscape.md`。情報源のある市場データ、競合マトリックス、狩野モデルの分割、および PoD/PoP 戦略の推奨が含まれます。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/revenue-models.md` | TAM/SAM/SOM のサイズ設定、収益モデルの分類 |
| `@rules/product/positioning-kano-hook.md` | 競合マトリックス、PoD/PoP、狩野モデル（Kano） |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-vision` | Consumer — 市場の事実をビジョンボードと PR-FAQ に供給します |
| `/product:design-revenue` | Downstream — 収益モデルはこの市場の見解の上に構築されます |
| `/product:design-positioning` | Downstream — ポジショニングは PoD/PoP と狩野モデルの上に構築されます |
| `/product:adapt-change` | 市場が変わったときにこの Skill を再実行します |
