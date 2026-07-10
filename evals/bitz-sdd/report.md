# bitz-sdd 評価レポート（Phase 5b: MVC + Database 一気通貫検証）

- **評価日**: 2026-07-11
- **対象**: evals/bitz-sdd/（cases.md v1, runs 1〜4）、bitz-sdd プラグイン v1.2.0
- **評価者注**: 実行はサブエージェント（W6）、採点は発注側が成果物の実地検分と
  スクリプト独立再実行（`sdd_report.py` を採点者環境で再実行し exit 0 / 出力内容を確認）により実施

## サマリー

| 指標 | 結果 |
| --- | --- |
| ケース合格率 | 3/3 |
| アサーション合格率 | 15/15 |
| 判定不能 | 0件 |

**総合判定: bitz-sdd v1.2.0 は MVC + Database 型の開発に対応している。**
ToDo アプリ題材で discovery → design → data → ops → review → report が bitz-ddd 未導入のまま
一気通貫で完走し、データ層の成果物（ER 図・証拠駆動の格納方式選定・MVC レイヤリング対応）が
`.spec/` に揃い docs/ へ同期された。マスタープラン Phase 5b の完了条件を満たす。

## ケース別結果

### TC-01: MVC + DB 題材の一気通貫設計 — 合格（8/8）
- ✅ `.spec/discovery/` に成果物: runs/1/todo-app/.spec/discovery/{vision.md, scope.md} が存在
- ✅ `.spec/design/domain-model.md`: 存在。bitz-ddd なしの軽量ドメインスケッチとして成立
- ✅ `.spec/design/data-model.md` に ER 図と格納方式選定: `erDiagram` を含み、適合性評価（Adopt/Reject + 根拠引用）の表あり
- ✅ `architecture.md` にレイヤリング: 「論理ビュー（MVCレイヤリング）」節と「レイヤー×技術×適合性×根拠」の表を確認
- ✅ `.spec/reviews/` にレビュー結果: review-synthesis.md（frontmatter `decision: CONDITIONAL_PASS`、major 指摘2件の実態に即した判定）
- ✅ `sdd_report.py` で status-report.md 生成: 実行ログ exit 0 + **採点者が独立再実行して exit 0 と CONDITIONAL_PASS の反映を確認**
- ✅ `sdd_sync.py pull` で docs へ同期: runs/1/todo-app/docs/02-design/data-model.md が存在（新設マッピングが機能）
- ✅ bitz-ddd 未導入で完走: log.md に軽量スケッチ分岐の使用を記録、途中で工程が止まった形跡なし

### TC-02: sdd-data の発動判定 — 合格（4/4）
- ✅ (a) 格納方式の相談 → 使う: description のトリガー「格納方式」に直接該当（runs/3/log.md）
- ✅ (b) テーブル設計レビュー → 使う: トリガー「テーブル設計」該当
- ✅ (c) ステートレス CLI → 使わない: description の「永続化しないシステムでは不要」に該当
- ✅ (d) UI 配色 → 使わない: 該当トリガーなし

### TC-03: DB を使わないシステムでの工程スキップ — 合格（3/3）
- ✅ sdd-data が強制されない: runs/4/log.md にフェーズ表と description 両方を根拠にした明示的なスキップ判断を記録
- ✅ data-model.md を作らない: runs/4/calc-cli/.spec/design/ は domain-model.md と architecture.md のみ
- ✅ design → review は成立: review-synthesis.md（PASS）が存在

## スキルあり / ベースライン比較所見（TC-01, runs/1 vs runs/2）

- **構造**: スキルありは `.spec/`（マスター）+ `docs/`（同期先）の規定構造・frontmatter（DSN ID・status）付き。ベースラインは独自の平坦な連番ファイル（01_requirements 〜 06_task_breakdown）で、機械検証（sdd_report / sdd_sync / spec_inspect）に接続できない
- **データ設計の質**: 両者とも DB スキーマは書けるが、ベースラインは SQLite 前提を無根拠に即決。スキルありは格納方式を証拠駆動（scope からの引用付き）で評価し、Reject 理由も記録しており、判断の可逆性が保たれている
- **ゲート接続**: スキルありはレビュー判定（CONDITIONAL_PASS + 条件リスト）が status-report に自動集計され Design Gate の材料になる。ベースラインには検証・ゲートの概念そのものがない
- 結論: 「仕様駆動で」という曖昧な依頼に対し、スキルの有無で成果物の**検証可能性**が質的に異なる。スキルの効果は明確に観測できた

## 改善提案（優先度順）

1. **（中）`decision` frontmatter の仕様明文化**: `sdd_report.py` は review-synthesis.md の
   frontmatter `decision:` を集計に使うが、公開契約（sdd-core assets/artifact-frontmatter.md）にも
   sdd-review の SKILL.md 本文にも記載がなく、実行者がソースを読んで初めて判明した
   （runs/1/log.md に記録）。契約側に `decision` キーを明記すべき
2. **（低）api-design.md の任意性の明記**: TC-01 で api-design.md 未作成のまま sync が SKIP と
   なったのは正しい挙動だが、sdd-design の成果物表では必須に見える。任意/必須の区別を表に足すとよい

## 次工程

- 改善提案1は仕様の記載漏れ（スキル本体の修正）にあたるため、別途 spec-issue / 修正 PR として扱う
- 全ケース合格のため、eval としてはこれで完了とする
