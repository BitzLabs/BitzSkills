# Run 1
- **ケース**: TC-01
- **モード**: スキルあり
- **実行日時**: 2026-07-11 03:50

## 手順の記録

1. `sdd-core` の SKILL.md を読み、フェーズ・ルーティング表から Discovery → Design（domain→data→architecture→ops）→ Review → Report/Docs の順序を確認。
2. `sdd-discovery` の SKILL.md（6ステップワークフロー）に従い、`.spec/discovery/vision.md`（DSC-001, Vision Board + PR-FAQ 圧力試験）と `scope.md`（DSC-002, 制約→Kano→RICE→MoSCoW）を作成。frontmatter は `sdd-core/assets/artifact-frontmatter.md` の共通契約（id/title/status/version/updated/owner）に準拠。未検証の数値は `TBD` と明示（絶対規則に従い事実の捏造を回避）。
3. `sdd-design` の SKILL.md を確認。bitz-ddd 未導入前提のため「判断分岐」節に従い軽量ドメインスケッチを採用し、`.spec/design/domain-model.md`（DSN-001）に Task / TaskList エンティティと関係を記述。
4. `sdd-data` の SKILL.md と `references/storage-selection.md` を読み、論理ER図（`data-model.md`, DSN-002, Mermaid erDiagram）と証拠駆動の格納方式選定表（RDB=SQLite を Adopt、NoSQL/ファイル/キャッシュを Reject、根拠シグナルを scope.md/domain-model.md から引用）を作成。永続化戦略も同ファイルに記述。物理スキーマ・マイグレーション計画は `data-storage.md`（DSN-003）に分離（skill定義の「格納方式選定はdata-model.md、物理スキーマ・移行はdata-storage.md」に対応）。
5. `.spec/design/architecture.md`（DSN-004）に MVCの論理ビュー（Mermaid flowchart: View→Controller→Model→DB）、プロセスビュー、配置ビュー、技術適合性評価を作成。フレームワーク未選定をギャップとして明示。
6. `sdd-ops` の SKILL.md を確認し、個人用途のため軽量成果物として `observability.md`（INF-001）のみ作成（インフラ構成・DR・コスト見積もりはNon-Goal個人用途につきスキップ、その旨を本文に明記）。
7. `sdd-review` の SKILL.md と `assets/review-registry.json`（5観点・重み・quality_gates）を読み、`.spec/reviews/review-synthesis.md`（REV-001）に5観点（consistency/data-integrity/operations/risk/business）のスコアと指摘（OPS-001, RSK-001, DIN-001）を記録。統合判定は実態（major指摘2件、operationsスコアが境界値）に基づき **CONDITIONAL_PASS** とした。
8. `python3 plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py <todo-appパス>` を実行 → `SUCCESS: Report generated ... status-report.md` (exit 0)。初回実行時、review-synthesis.md の frontmatter に `decision` フィールドが無く「判定結果: なし / レビュー判定: PENDING」と表示される不整合を発見。sdd_report.py のソースを確認したところ frontmatter の `decision` フィールドを読む実装だったため、`decision: CONDITIONAL_PASS` を frontmatter に追記し再実行。結果「判定結果: CONDITIONAL_PASS (条件付き合格)」に更新されたことを確認（exit 0）。
9. `python3 plugins/bitz-sdd/skills/sdd-docs/scripts/sdd_sync.py pull --root <todo-appパス>` を実行 → vision.md/scope.md/domain-model.md/architecture.md/data-model.md の5ファイルが `docs/01-context/` `docs/02-design/` へ展開されたことを確認（`SUCCESS [pull]` ×5、`api-design.md` は未作成のため `SKIP` と表示、exit 0）。

## 成果物

`evals/bitz-sdd/runs/1/todo-app/` 配下に以下をコピー保存:
- `.spec/discovery/vision.md`, `.spec/discovery/scope.md`
- `.spec/design/domain-model.md`, `data-model.md`, `data-storage.md`, `architecture.md`, `observability.md`
- `.spec/reviews/review-synthesis.md`
- `.spec/reports/status-report.md`
- `docs/01-context/mission-vision.md`, `non-goals.md`
- `docs/02-design/domain-model.md`, `ARCHITECTURE.md`, `data-model.md`

## 備考

- sdd-report が要求する `decision` frontmatter フィールドは、`sdd-core/assets/artifact-frontmatter.md`（公開契約）にも `sdd-review` の SKILL.md 本文にも明記されておらず、`sdd_report.py` のソースを読んで初めて判明した。ドキュメント記載漏れの可能性があるため、司令塔側での確認を推奨（本eval実行では修正せず、実測どおり記録）。
- `sdd-data` は sdd-design と sdd-ops の中間に位置づけられる工程だが、SKILL.md表中の「工程内での位置づけ」節どおり `domain-model.md` → `data-model.md`/`data-storage.md` → `architecture.md`（データ層記述含む）→ `observability.md` の順で無理なく統合できた。
- api-design.md は本ケースのプロンプトに API 設計の要求がなく（画面・サーバー・DB のみ）、スコープ外として作成しなかった。sdd_sync.py pull もこれを `SKIP` として正しく扱った。
- review-synthesis.md の判定は「実態に即して」との指示どおり、フレームワーク未選定・バックアップ手順未記載の2件の major 指摘を理由に CONDITIONAL_PASS とした（PASS ではない）。
