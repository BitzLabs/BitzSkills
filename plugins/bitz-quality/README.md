# bitz-quality プラグイン

BitzQuality は、AI駆動の品質管理（QA）、多層品質ゲート、テスト自動設計、および多観点レビューを提供するプラグインです。
アルダグラム社による実務実践モデル（`qa-orchestrator` / プール制QA & 5軸リスクスコアリング / 静的×LLM×Hooks の3層ゲート）を完全統合し、仕様駆動開発（`bitz-sdd`）および PR フロー（`bitz-flow`）と連携して「最速で最高品質を届ける自律QA体制」を実現します。

## スキル一覧（全8スキル）

1. **`quality-core`**: メインスキル。QAプロセス全体を対話型で統括し、専門サブエージェント群をオーケストレーションする。
2. **`quality-init`**: プロジェクトへ `.spec/quality/` ディレクトリと Git hooks（pre-commit / pre-push）を初期化・配備する。
3. **`quality-doctor`**: 品質環境、hooks、スキーマ整合性、未レビュー差分を読み取り専用で診断する。
4. **`quality-score`**: 5軸（規模・セキュリティ・影響・難易度・習熟度）で施策リスクを評価し、関与レベル（A/B/C）を自動判定する。
5. **`quality-gate`**: 静的チェック（S01〜S10）× 読み取り専用LLMレビュー（L01〜L11）× pre-push による3層品質ゲートを強制する。
6. **`quality-review`**: 仕様・コード・スキル・テストの多観点レビューを実行し、指摘から再発防止ルール（`general_rule`）を自律蓄積する。
7. **`quality-design`**: 5つの専門サブエージェント（影響分析・不具合分析・観点・ケース・データ）によるテスト設計を自動化する。
8. **`quality-measurand`**: EARS 数値要件に対する測定定義（分母・proxy・除外規則）と検証履歴をモデル化する。

## 成果物スキーマ（`.spec/` 統合）

```text
.spec/
├── quality/               # bitz-quality 成果物
│   ├── sessions/          # qa-session.json（オーケストレーション進捗）
│   ├── scorings/          # 5軸リスクスコアリング & 関与レベル判定結果
│   ├── analyses/          # 影響分析 / 不具合傾向分析レポート
│   ├── viewpoints/        # テスト観点一覧設計書
│   ├── reports/           # quality-summary.md（リリース判定サマリー）
│   └── rules/             # 再発防止ルール台帳 (自律進化ルール)
├── reviews/               # 多観点レビュー結果・ReviewFinding
└── verification/          # 検証証跡 (verification-evidence)
```
