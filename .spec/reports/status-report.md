# BitzSDD status-report

生成日時: 2026-07-22 21:41:54

## 1. 総合サマリー
| メトリクス | 現在のステータス |
| :--- | :--- |
| **総合ヘルス** | **GREEN** |
| **要件進捗率 (Verified/Promoted)** | **100%** (27 / 27 要件) |
| **ディスカバリー状況** | 検証ゲート合格 (Go) |
| **設計レビュー結果** | PASS (合格) |

---

## 2. 要件ライフサイクル状況 (27 件)
*   **起草中（draft）**: 0 件
*   **承認済み（approved）**: 0 件
*   **実装中（implementing）**: 0 件
*   **検証済み（verified）**: 27 件
*   **確定（promoted）**: 0 件

### 要件一覧
| 要件ID | タイトル | ステータス |
| :--- | :--- | :--- |
| CORE-CON-001 | 3マニフェストの version 同値 | 検証済み（verified） |
| CORE-CON-002 | SKILL.md frontmatter の metadata 必須 | 検証済み（verified） |
| CORE-CON-003 | marketplace.json と plugins/ 実体の双方向整合 | 検証済み（verified） |
| CORE-CON-004 | スキルの自己完結 | 検証済み（verified） |
| CORE-CON-005 | プラグイン内スキル名の単一プレフィックス | 検証済み（verified） |
| CORE-CON-006 | コミット・PR タイトルの Conventional Commits 準拠 | 検証済み（verified） |
| CORE-CON-007 | 委譲の損益分岐と過剰委譲防止 | 検証済み（verified） |
| CORE-CON-008 | 共通ライフサイクルスキル標準 init/doctor/update/uninstall | 検証済み（verified） |
| CORE-CON-009 | update のバージョン移行（マイグレーション）機構 | 検証済み（verified） |
| CORE-CON-010 | version bump の PR 内配置規約 | 検証済み（verified） |
| CORE-FR-001 | sdd-design 成果物表の必須/任意の明示 | 検証済み（verified） |
| CORE-FR-002 | spec_inspect の自己言及 ID の幽霊参照除外 | 検証済み（verified） |
| CORE-FR-003 | spec_status.py による軽量状況照会 | 検証済み（verified） |
| CORE-FR-004 | spec_scaffold.py による採番付き雛形生成 | 検証済み（verified） |
| CORE-FR-005 | spec_update.py による status 遷移の権限強制と STATE.md 更新 | 検証済み（verified） |
| CORE-FR-006 | Execute 委譲ゲート（役割分類と委譲判定の提示） | 検証済み（verified） |
| CORE-FR-007 | 相対選択：下位ティアへの委託 | 検証済み（verified） |
| CORE-FR-008 | 相対選択：上位ティアへの相談・上申 | 検証済み（verified） |
| CORE-FR-009 | プラットフォーム別委譲レジストリ（役割→委譲先→ティアの SSOT） | 検証済み（verified） |
| CORE-FR-010 | spec_scaffold.py の生成時語彙検証と DSN 種別の追加 | 検証済み（verified） |
| CORE-FR-011 | scripts/spec ラッパーによる SDD ツールのバージョン非依存解決 | 検証済み（verified） |
| CORE-FR-012 | spec_status.py による accepted 未着手 spec-issue の検知 | 検証済み（verified） |
| CORE-FR-013 | release_check.py によるプラグイン間依存の宣言と検証 | 検証済み（verified） |
| CORE-FR-014 | bitz-flow プラグインの新設（sdd-git の汎用化転記） | 検証済み（verified） |
| CORE-FR-015 | bitz-flow 定型処理スクリプト（worktree_ops / commit_lint / pr_helper） | 検証済み（verified） |
| CORE-FR-016 | sdd-git の縮退（Git フローの正を bitz-flow へ一本化） | 検証済み（verified） |
| CORE-NFR-001 | 委譲レジストリ整合の機械検証 | 検証済み（verified） |

---

## 3. 設計確立状況 (.spec/design/)
*   **ドメインモデル (domain-model.md)**: 未作成
*   **API設計 (api-design.md)**: 未作成
*   **アーキテクチャ設計 (architecture.md)**: 未作成

---

## 4. レビュー状況 (.spec/reviews/)
*   **統合ステータス**: 1 件のレビューが存在
*   **判定結果**: PASS (合格)

### レビュー報告書一覧
| ファイル名 | レビュー判定 |
| :--- | :--- |
| review-synthesis.md | `PASS` |

---

## 5. タスク実行状況 (.spec/tasks/ - 24 件)
*   **着手待ち（pending）**: 0 件
*   **実装中（implementing）**: 0 件
*   **介入待ち（blocked）**: 0 件
*   **完了（done）**: 24 件
