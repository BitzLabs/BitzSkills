---
description: |
  すべてのプロダクト成果物を、必須の「主な仮定と検証状況（Key Assumptions & Validation Status）」セクション（ゲートの判定、未解決の仮定、すべての TBD、および未解決の質問（Open Questions）を含む）を冒頭に配置した、自己完結型の1つの HTML レポート（Mermaid インライン）に統合します。これは、他のデザインコンテンツよりも前に配置されます。/product:report [--auto] [--lang=ja|en]。
model: sonnet
user_invocable: true
---

# Consolidated Report

## Desired Outcome

1つの成果物を作成します：

1. **完全なレポート（Full report）** — `reports/report/full-report.html`:
   - **「主な仮定と検証状況（Key Assumptions & Validation Status）」から始まる** — ゲートの判定、しきい値を持つ未テスト/未解決の仮定、すべての `TBD` / `TBD-assumption`、および未解決の質問（Open Questions）
   - その後、パイプライン順のフェーズごとのセクションが続き、それぞれがソースファイルにリンクします
   - Mermaid ダイアグラムはインラインでレンダリングされます。自己完結型（インライン CSS）であり、Mermaid ランタイム以外の外部アセットはありません

## Invocation

```
/product:report [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | 存在するすべての成果物から生成します |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **仮定を最初に。** 検証状況は一番上に配置されます — 読者はデザインを読む前に、何が賭け（bet）であるかを確認しなければなりません。
- **「パス」を決してでっち上げない。** 成果物の欠落や `no-go`（不合格）の判定は、目立つように記載します。
- **自己完結型。** インライン CSS。Mermaid のレンダリング。壊れた外部リンクがないこと。
- **終了条件（Stop condition）**: 主な仮定のセクションが存在し完全であること、既存のすべての成果物がパイプライン順に含まれていること、および Mermaid ブロックがレンダリングされていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/**/*.md` | Required | 過去のすべての Skills | 存在するものは何でも含めます。フェーズの欠落を書き留めます |
| `work/pipeline-progress.json` | Required | `/product:init-output` | ゲートの判定を報告します。存在しない場合は `TBD` とマークします |
| `reports/00_core/assumptions.md` | Recommended | `/product:validate-assumptions` | 仮定のセクションは「まだ検証されていません」にダウングレードします |
| `work/context.md` | Recommended | すべての Skills | 未解決の質問（Open Questions）セクションは `TBD` にダウングレードします |

## Process

1. **収集（Collect）** — すべての `reports/**/*.md`、ゲートの判定、仮定、および未解決の質問（Open Questions）を収集します。
2. **ヘッダーの構築（Build the header）** — ゲート、未解決の `ASM-`、すべての `TBD`、および未解決の質問から「主な仮定と検証状況（Key Assumptions & Validation Status）」を組み立てます。`@rules/product/review-and-report.md` を適用します。
3. **本文の組み立て（Assemble body）** — パイプライン順にフェーズごとのセクションを設け、ソースファイルをリンクします。Mermaid をレンダリングします。
4. **自己完結化（Self-contain）** — インライン CSS。壊れた参照がないことを確認します。
5. **記録** — `full-report.html` を書き込みます。`work/context.md` にメモを追記します。

## Output

`reports/report/full-report.html`。冒頭に検証状況があり、すべての成果物が統合されています。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/review-and-report.md` | レポートの構造と、必須の仮定ヘッダー |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:review` | Upstream — 発見事項（findings）はレポートで表面化できます |
| `/product:validate-assumptions` | Upstream — ゲートの判定と未解決の仮定を提供します |
| `/product:start` | Orchestrator — 通常、最終ステップとして `report` を実行します |
