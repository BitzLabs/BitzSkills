---
description: |
  収益/ビジネスモデルと再計算可能な利益評価テンプレート — Lean Canvas/BMC、選択された収益モデル、ユニットエコノミクス方程式（LTV/CAC、回収期間、ROI/NPV）、および反証可能な価値仮説 — を設計します。価格と CAC は事実として計算されるのではなく、validate-assumptions に送られます。
  /product:design-revenue [--input=<file|dir>] [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Revenue Model & Benefit Evaluation

## Desired Outcome

2つの成果物を作成します：

1. **収益モデル（Revenue model）** — `reports/00_core/revenue-model.md`（`REV-` IDs）:
   - **Lean Canvas / BMC** — 9つのブロック（新規/不確実なプロダクトのための Lean Canvas）
   - **収益モデルの選択（Revenue model selection）** — どのパターンか、そして*なぜそれが創出される価値に適合するのか*
2. **利益評価（Benefit evaluation）** — `reports/00_core/benefit-evaluation.md`:
   - **定量的（再計算可能なテンプレート）（Quantitative (recomputable template)）** — LTV、CAC、LTV:CAC（≥3 のベンチマーク）、CAC 回収期間（payback）、ROI/NPV — 入力を伴う数式。価格/CAC は固定の数値ではなく `TBD-assumption` です
   - **定性的（Qualitative）** — 「X を出荷すれば、Y 指標が T 以内に Z% 動く」という形式の価値仮説（`NSM-` を参照）。それぞれに検証方法が付きます

## Invocation

```
/product:design-revenue [--input=<file|dir>]... [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--input=<file\|dir>` | Optional, repeatable | 価格設定の資料、財務上の仮定、過去のモデル |
| `--auto` | Optional | ファシリテーションをスキップします。不明点は `TBD` / `TBD-assumption` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **価格と CAC は仮定であり、算術ではありません。** これらを `TBD-assumption` として記録し、`/product:validate-assumptions` に渡して市場でテストします（Van Westendorp、プレセール）。スプレッドシートの出力を確立された事実として提示しないでください。
- **モデルは価値がどのように提供されるかに適合していなければならない** — 選択した収益パターンを正当化し、単に名前を挙げるだけにしないでください。
- **ユニットエコノミクスはテンプレートであり、評決ではありません** — 実際の証拠が届いたときに再計算できるように数式を設定します。LTV:CAC ≥ 3 / 回収期間 < 12ヶ月のベンチマークにフラグを立てます。
- **すべての価値仮説は反証可能であり**、`NSM-` 指標を参照します。
- **終了条件（Stop condition）**: キャンバス上に正当化された収益モデル、仮定がフラグ付けされた再計算可能なユニットエコノミクステンプレート、および反証可能な価値仮説が存在すること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/00_core/vision-mission-value.md` | Required | `/product:define-vision` | メッセージを出してブロックする |
| `reports/00_core/success-metrics.md` | Recommended | `/product:define-success-metrics` | 価値仮説に `NSM-` アンカーが不足しています。`TBD` とマークします |
| `reports/00_core/market-landscape.md` | Optional | `/product:research-landscape` | 進行します。存在する場合はサイジング/価格設定のコンテキストを取得します |

## Process

1. **コンテキストの読み取り** — ビジョン、サクセスメトリクス、市場ランドスケープ、`work/traceability.json`。
2. **キャンバス（Canvas）** — 上流の成果物から Lean Canvas/BMC の 9つのブロックを埋めます。
3. **モデルの選択（Select model）** — 収益パターンを選択し、その適合性を正当化します。`@rules/product/revenue-models.md` を適用します。
4. **定量的テンプレート（Quantitative template）** — LTV/CAC/回収期間/ROI/NPV の数式を設定します。ゲートのために価格と CAC を `TBD-assumption` としてマークします。
5. **定性的（Qualitative）** — `NSM-` を参照しながら、検証方法を伴う価値仮説（「X を出荷すれば、Y 指標が Z% 動く」）を記述します。
6. **トレーサビリティの追記** — 上流の `VIS-`/`NSM-` 参照を持つ `REV-` ノードを `work/traceability.json` に追加します。`validate-assumptions` が拾えるように `TBD-assumption` 項目をマークします。
7. **記録** — 両方のファイルを書き込みます。決定事項を `work/context.md` に追記します。仮定を未解決の質問（Open Questions）にログとして記録します。

## Output

`reports/00_core/revenue-model.md` と `reports/00_core/benefit-evaluation.md`、`REV-` ID テーブル（Upstream 列を含む）があり、価格/CAC は `TBD-assumption` としてフラグ付けされています。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/revenue-models.md` | BMC/Lean Canvas、収益の分類、ユニットエコノミクス、価値仮説 |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-vision` | Upstream — ビジネス目標はここから発生します |
| `/product:define-success-metrics` | Upstream — 価値仮説は `NSM-` 指標を動かします |
| `/product:research-landscape` | Upstream (optional) — 市場規模と価格設定のコンテキスト |
| `/product:validate-assumptions` | Downstream — 価格/CAC の `TBD-assumption` はここで検証されます |
| `/product:adapt-change` | 経済性が変わったときにこの Skill を再実行します |
