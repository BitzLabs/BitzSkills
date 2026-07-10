---
description: |
  Jobs-to-be-Done にアンカーされたペルソナを生成します — ジョブストーリー（job stories）とペルソナカード（コンテキスト、pains、gains、JTBD、逐語録（verbatim））— これは、証拠が集まるにつれてリサーチベースに昇格するプロトペルソナ（proto-persona）のスキャフォールドとして機能します。人口統計（demographics）や引用（quotes）を決してでっち上げません。
  /product:generate-persona [--input=<file|dir>] [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Personas (Jobs-to-be-Done)

## Desired Outcome

1つの成果物を作成します：

1. **ペルソナ（Personas）** — `reports/01_ux/personas.md`:
   - **ジョブストーリー（Job stories）**（`JOB-` IDs） — *[状況] のとき、私は [動機付け] したい、そうすれば [結果] できる（When [situation], I want to [motivation], so I can [outcome]）*。機能的（functional）/ 感情的（emotional）/ 社会的（social）な側面をカバーします。
   - **ペルソナカード（Persona cards）**（`PER-` IDs） — アーキタイプ（archetype）、コンテキストと行動、JTBD、ペイン（Pains）、ゲイン（Gains）、および逐語の引用（未検証の場合は `[proto]` とマークします）。
   - 指定された**プライマリペルソナ（primary persona）** と、セカンダリ / アンチペルソナ。

ペルソナは（ピボットを生き延びる）ジョブにアンカーされており、人口統計（demographics）にはアンカーされていません。未検証のコンテンツは明示的に**プロトペルソナ（proto-persona）**のスキャフォールドです。

## Invocation

```
/product:generate-persona [--input=<file|dir>]... [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--input=<file\|dir>` | Recommended | インタビューメモ、アンケート、アナリティクス、サポートログ |
| `--auto` | Optional | ファシリテーションをスキップします。入力のみからプロトペルソナを生成します |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **人口統計ではなくジョブにアンカーする。** すべてのペルソナは、少なくとも1つの `JOB-` ストーリーを保持している必要があります。
- **AIの出力はスキャフォールドです。** 未検証の主張には `[proto]` とマークします。感情的な妥当性はリサーチがそれを確認するまで弱いものです。リサーチデータが存在する場合は、どこでもそれを優先します。
- **人口統計や引用を決してでっち上げないこと。** 不明点は未解決の質問（Open Questions）で `TBD` とします。
- **プライマリペルソナを指名する** — プロダクトは「すべての人」のために最適化することはできません。
- **終了条件（Stop condition）**: ペルソナごとに ≥1 つのジョブストーリーがあり、各ペルソナカードが完成している（または `TBD`/`[proto]` になっている）こと、およびプライマリペルソナが指定されていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/00_core/vision-mission-value.md` | Required | `/product:define-vision` | メッセージを出してブロックする — ペルソナにはターゲットグループが必要です |
| リサーチ資料 (`--input`) | Recommended | User | プロトペルソナとして進行します。`[proto]` とマークします |

## Process

1. **コンテキストの読み取り** — ビジョン（ターゲットグループ）、`work/context.md`、`work/traceability.json`、`--input`。
2. **ジョブの抽出（Extract jobs）** — ターゲットグループの状況からジョブストーリー（機能的/感情的/社会的）を記述します。`@rules/product/persona-jtbd.md` を適用します。
3. **カードの構築（Build cards）** — コンテキスト、ペイン（Pains）、ゲイン（Gains）、JTBD、逐語録（リサーチに基づくもの。それ以外は `[proto]`）。
4. **優先順位付け（Prioritize）** — プライマリペルソナと、セカンダリ/アンチペルソナを指定します。
5. **トレーサビリティの追記** — 上流の `VIS-` 参照を持つ `JOB-`/`PER-` ノードを `work/traceability.json` に追加します。
6. **記録** — ファイルを書き込みます。決定事項を `work/context.md` に追記します。`TBD`/`[proto]` 項目をログに記録します。

## Output

`reports/01_ux/personas.md`、`JOB-`/`PER-` ID テーブル（Upstream 列を含む）があり、プライマリペルソナがフラグ付けされています。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/persona-jtbd.md` | JTBD ジョブストーリー、ペルソナカード、プロト（proto）vs リサーチベース |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-vision` | Upstream — ターゲットグループを提供します |
| `/product:map-journey` | Downstream — 各ペルソナのジャーニーをマッピングします |
| `/product:define-features` | Downstream — 機能は `JOB-`/`PER-` に奉仕します |
| `/product:adapt-change` | オーディエンスが変更されたときにこの Skill を再実行します |
