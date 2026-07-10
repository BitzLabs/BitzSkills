---
description: |
  顧客の期待からサービスレベルの目標を設定します — サービスごとの SLI/SLO/SLA にエラーバジェットとクリティカリティの階層を伴います。ここで SLO = SLA - バッファです。/product:design-sla [--auto] [--lang=ja|en]。
model: sonnet
user_invocable: true
---

# SLA Design

## Desired Outcome

1つの成果物を作成します：

1. **SLA** — `reports/04_quality/sla.md`（`SLA-` / `SLO-` IDs）: サービスごとの **SLI / SLO / SLA**、**error budget（エラーバジェット）**（`1 − SLO`）とそのポリシー、および**クリティカリティの階層（criticality tiers）**（critical / standard / best-effort）。目標は顧客の期待に一致し、SLO は SLA よりも厳格です。

## Invocation

```
/product:design-sla [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしで導出します。欠落しているターゲットは `TBD` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **SLO = SLA − バッファ。** 内部の目標は、外部への約束よりも常に厳格です。
- 切りりの良い数字ではなく、**顧客の期待に合わせる** — ポジショニング/利益から期待を引き出します。
- **クリティカリティによる階層化** — すべてのサービスに同じレベルが必要なわけではありません。
- クリティカルなサービスに対する error budget（`1 − SLO`）とフリーズ/リリース ポリシーを明記します。
- **終了条件（Stop condition）**: 各主要サービスに、SLI、SLO、バッファを伴う SLA、error budget、およびクリティカリティの階層が存在すること（数値は `TBD` でも可）。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/02_spec/feature-list.md` | Required | `/product:define-features` | メッセージを出してブロックする — SLA はサービス/機能に付加されます |
| `reports/01_ux/positioning.md` | Recommended | `/product:design-positioning` | 顧客の期待は `TBD` にダウングレードします |
| `reports/00_core/benefit-evaluation.md` | Optional | `/product:design-revenue` | 存在する場合は価値/クリティカリティの重み付けに使用します |

## Process

1. **コンテキストの読み取り** — 機能、ポジショニング（期待）、利益評価、`work/traceability.json`。
2. **SLI の定義（Define SLIs）** — 各主要サービスにとって重要なシグナル。`@rules/product/sla-nfr.md` を適用します。
3. **SLO の設定（Set SLOs）** — 顧客の期待に沿ったターゲットを設定し、クリティカリティで階層化します。
4. **SLA の明記（State SLAs）** — SLO を下回るバッファを持った外部への約束。
5. **エラーバジェット（Error budgets）** — `1 − SLO` を計算します。ポリシーを明記します。
6. **トレーサビリティの追記** — 上流の `FEAT-`/`POS-` 参照を持つ `SLA-`/`SLO-` ノードを `work/traceability.json` に追加します。
7. **記録** — ファイルを書き込みます。決定事項を `work/context.md` に追記します。`TBD` をログに記録します。

## Output

`reports/04_quality/sla.md`、`SLA-`/`SLO-` テーブル（Upstream 列を含む）、error budget、および階層が含まれます。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/sla-nfr.md` | SLI/SLO/SLA、error budget、クリティカリティの階層 |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-features` | Upstream — レベルを設定する対象となるサービス/機能 |
| `/product:design-positioning` | Upstream — 顧客の期待 |
| `/product:define-nfr` | Downstream — NFR はこれらの SLO から派生します |
| `/product:adapt-change` | 期待が変更されたときにこの Skill を再実行します |
