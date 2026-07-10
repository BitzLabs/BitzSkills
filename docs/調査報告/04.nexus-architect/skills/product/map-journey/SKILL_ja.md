---
description: |
  各プライマリペルソナのカスタマージャーニーを、ステージ（stages）× レイヤー（layers）のグリッド — タッチポイント、アクション、逐語の感情、ペイン、機会（opportunities） — としてマッピングし、真実の瞬間（Moments of Truth）にフラグを立てて、優先順位付けされた機会のリストを生成します。/product:map-journey [--auto] [--lang=ja|en]。
model: sonnet
user_invocable: true
---

# Customer Journey Maps

## Desired Outcome

1つの成果物を作成します：

1. **ジャーニーマップ（Journey maps）** — `reports/01_ux/journey-maps.md`（`JNY-` IDs）:
   - プライマリペルソナごとに1つのマップ: **ステージ（stages）**（認知（Awareness）→ 検討（Consideration）→ 購入（Purchase）→ オンボーディング（Onboarding）→ 利用（Usage）→ 更新（Renewal）→ 推奨（Advocacy））×
   - **レイヤー（layers）**: タッチポイント/チャネル、アクション、思考と感情（**逐語録（verbatim）** + 感情曲線（emotion curve））、ペインポイント、機会（opportunities）
   - **真実の瞬間（Moments of Truth）**（ZMOT / FMOT / SMOT）がフラグ付けされ、特に感情曲線が落ち込む部分に注目します
   - 優先順位付けされた**機会のリスト（opportunity list）**（これが実際の出力です）

## Invocation

```
/product:map-journey [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしでペルソナから生成します。想定されるエントリは `[proto]` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **すべての行をペルソナのジョブに基づかせる。** ペイン/機会は `JOB-`/`PER-` IDs に結び付きます。
- 可能な限り**感情を逐語的（verbatim）に捉える**。感情曲線は落ち込みを可視化しなければなりません。
- **感情を発明しない。** 想定されるエントリは、検証されるまでは `[proto]` となります。
- **真実の瞬間（Moments of Truth）にフラグを立てる** — MoT における落ち込みは、最もレバレッジの高い修正ポイントです。
- **終了条件（Stop condition）**: 各プライマリペルソナに MoT がフラグ付けされたステージ×レイヤーマップと、優先順位付けされた機会のリストが存在すること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/01_ux/personas.md` | Required | `/product:generate-persona` | メッセージを出してブロックする — ジャーニーにはペルソナが必要です |

## Process

1. **コンテキストの読み取り** — ペルソナ（プライマリペルソナに焦点を当てる）、`work/traceability.json`。
2. **ステージのレイアウト（Lay out stages）** — デフォルトの骨格をプロダクト/ペルソナに適応させます。
3. **レイヤーの記入（Fill layers）** — ステージごとに、タッチポイント、アクション、逐語の感情 + 曲線、ペイン、機会を記入します。`@rules/product/journey-mapping.md` を適用します。
4. **MoT のフラグ付け（Flag MoTs）** — ZMOT/FMOT/SMOT と感情の落ち込みをマークします。
5. **機会の優先順位付け（Prioritize opportunities）** — レバレッジ（ペインの深刻度 × 頻度）でランク付けします。
6. **トレーサビリティの追記** — 上流の `PER-`/`JOB-` 参照を持つ `JNY-` ノードを `work/traceability.json` に追加します。
7. **記録** — ファイルを書き込みます。決定事項を `work/context.md` に追記します。`[proto]`/`TBD` 項目をログに記録します。

## Output

`reports/01_ux/journey-maps.md`、`JNY-` ID テーブル（Upstream 列を含む）、および優先順位付けされた機会のリストが含まれます。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/journey-mapping.md` | ステージ × レイヤー、感情曲線、真実の瞬間（Moments of Truth） |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:generate-persona` | Upstream — ここでマッピングされるペルソナを提供します |
| `/product:design-positioning` | Downstream — タッチポイントはポジショニングマトリックスに供給されます |
| `/product:generate-ui-mock` | Downstream — モックはジャーニーの機会（opportunities）に対処します |
| `/product:adapt-change` | 行動が変わったときにこの Skill を再実行します |
