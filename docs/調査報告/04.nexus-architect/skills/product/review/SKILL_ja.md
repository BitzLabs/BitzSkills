---
description: |
  蓄積されたプロダクト成果物を4つのレンズ — 一貫性（consistency）、トレーサビリティ（traceability）、拡張性（extensibility）、および戦略（strategy） — を通してレビューし、アクション可能な発見事項（findings）のリスト（重要度 + 場所 + 修正案）を返します。
  再実行可能であり、パイプラインの途中で実行できます。/product:review [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Multi-Lens Review

## Desired Outcome

1つの成果物を作成します：

1. **レビュー（Review）** — `reports/report/review.md`: 4つのレンズからの発見事項。それぞれに**レンズ、重要度（blocker / major / minor）、場所（ファイル + ID）、および具体的な修正案**が伴います:
   - **一貫性（Consistency）** — 壊れた ID 参照、矛盾、用語のズレ（drift）
   - **トレーサビリティ（Traceability）** — `work/traceability.json` とドキュメントの比較。孤立した参照（orphans）とぶら下がった参照（dangling refs）
   - **拡張性（Extensibility）** — ドメインの境界と API の再利用 vs 将来の機能
   - **戦略（Strategy）** — ビジョン↔スコープの整合性、ユニットエコノミクスの健全性、持続可能な差別化

## Invocation

```
/product:review [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしで実行します。存在するすべての成果物について報告します |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **表面的なものではなく、アクション可能であること。** すべての発見事項には、重要度、場所（ファイル + ID）、および修正案が必要です。
- **目標と作業の不一致（goal–work misalignment）を表面化する**（戦略レンズ）。単なるタイプミスではありません。
- **「パス」を決してでっち上げない。** 欠落している成果物や `no-go`（不合格）の判定は、発見事項として報告されます。
- **終了条件（Stop condition）**: 4つのレンズすべてが利用可能な成果物に適用され、発見事項が重要度順にランク付けされていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/01_ux/journey-maps.md` | Required (minimum) | `/product:map-journey` | メッセージを出してブロックする — これより前ではレビューするものが少なすぎます |
| 後のフェーズの成果物 | Optional | spec/domain/quality スキル | 存在するもののみをレビューします。カバレッジのギャップを書き留めます |
| `work/traceability.json` | Recommended | すべての Skills | トレーサビリティレンズがダウングレードします。それを書き留めます |

## Process

1. 既存のすべての成果物と `work/traceability.json` を**読む（Read）**。
2. **一貫性レンズ（Consistency lens）** — ID の使用と用語をクロスチェックします。`@rules/product/review-and-report.md` を適用します。
3. **トレーサビリティレンズ（Traceability lens）** — グラフを検証します。孤立した参照やぶら下がった参照にフラグを立てます。
4. **拡張性レンズ（Extensibility lens）** — 将来の機能に対して、ドメイン境界と API の再利用をテストします。
5. **戦略レンズ（Strategy lens）** — ビジョン↔スコープ、経済性、差別化の持続可能性。
6. **ランク付けと記録（Rank & record）** — 発見事項を重要度順に並べ替えます。ファイルを書き込みます。要約を `work/context.md` に追記します。

## Rerun

成果物が蓄積されるにつれて、パイプラインの途中で再実行できるように設計されています — 存在するものは何でもレビューします。

## Output

`reports/report/review.md`。4つのレンズにわたる、重要度でランク付けされた発見事項のリスト。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/review-and-report.md` | 4つのレンズと発見事項の採点方法 |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:report` | Downstream — 成果物を統合します。レビューの発見事項を表面化します |
| `/product:validate-assumptions` | Related — ゲートの判定は戦略レンズに情報を提供します |
| `/product:adapt-change` | Related — レビューの発見事項が再伝播（re-propagation）のトリガーとなる場合があります |
