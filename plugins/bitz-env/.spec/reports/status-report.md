# BitzSDD status-report

生成日時: 2026-07-22 21:41:54

## 1. 総合サマリー
| メトリクス | 現在のステータス |
| :--- | :--- |
| **総合ヘルス** | **GREEN** |
| **要件進捗率 (Verified/Promoted)** | **100%** (19 / 19 要件) |
| **ディスカバリー状況** | 検証ゲート合格 (Go) |
| **設計レビュー結果** | PASS (合格) |

---

## 2. 要件ライフサイクル状況 (19 件)
*   **起草中（draft）**: 0 件
*   **承認済み（approved）**: 0 件
*   **実装中（implementing）**: 0 件
*   **検証済み（verified）**: 19 件
*   **確定（promoted）**: 0 件

### 要件一覧
| 要件ID | タイトル | ステータス |
| :--- | :--- | :--- |
| ENV-CON-001 | deny セットは普遍的最小集合に限定 | 検証済み（verified） |
| ENV-CON-002 | アダプタ契約の後方互換拡張 | 検証済み（verified） |
| ENV-CON-003 | 生成・記録は対象プロジェクト内に限定 | 検証済み（verified） |
| ENV-CON-004 | ガードの位置づけ（誤操作抑止・二重化前提） | 検証済み（verified） |
| ENV-FR-001 | 同梱フックによる破壊的操作の deny | 検証済み（verified） |
| ENV-FR-002 | フック入力のプラットフォーム自動判別と安全な失敗 | 検証済み（verified） |
| ENV-FR-003 | env-init のユーザー確認付き生成 | 検証済み（verified） |
| ENV-FR-004 | マーカー区間による再生成 | 検証済み（verified） |
| ENV-FR-005 | モデル非依存の役割割り当てと劣化動作・防御的協調 | 検証済み（verified） |
| ENV-FR-006 | 協調アダプタの契約チェックと登録・役割ルーティング | 検証済み（verified） |
| ENV-FR-007 | env-doctor による3層同期診断 | 検証済み（verified） |
| ENV-FR-008 | rules/*.md の両プラットフォーム読み込み | 検証済み（verified） |
| ENV-FR-009 | env-init 生成物の復旧可能性 | 検証済み（verified） |
| ENV-FR-010 | 生成物のトラッキングと env-uninstall による撤去 | 検証済み（verified） |
| ENV-FR-011 | env-update バージョン更新とマイグレーション機構 | 検証済み（verified） |
| ENV-FR-012 | bitz-env-version 未記録環境の stamp 後付け救済（env-doctor 検出 + env-update 救済フロー） | 検証済み（verified） |
| ENV-FR-013 | env-update dry-run の git 管理状態実確認と rollback 手段の正確な提示 | 検証済み（verified） |
| ENV-NFR-001 | ガードの応答時間 | 検証済み（verified） |
| ENV-NFR-002 | rules 注入サイズの節度 | 検証済み（verified） |

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

## 5. タスク実行状況 (.spec/tasks/ - 16 件)
*   **着手待ち（pending）**: 0 件
*   **実装中（implementing）**: 0 件
*   **介入待ち（blocked）**: 0 件
*   **完了（done）**: 16 件
