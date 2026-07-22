# BitzSDD status-report

生成日時: 2026-07-22 21:41:54

## 1. 総合サマリー
| メトリクス | 現在のステータス |
| :--- | :--- |
| **総合ヘルス** | **YELLOW (ドラフト状態の要件あり)** |
| **要件進捗率 (Verified/Promoted)** | **92%** (51 / 55 要件) |
| **ディスカバリー状況** | 検証ゲート合格 (Go) |
| **設計レビュー結果** | PASS (合格) |

---

## 2. 要件ライフサイクル状況 (55 件)
*   **起草中（draft）**: 4 件
*   **承認済み（approved）**: 0 件
*   **実装中（implementing）**: 0 件
*   **検証済み（verified）**: 51 件
*   **確定（promoted）**: 0 件

### 要件一覧
| 要件ID | タイトル | ステータス |
| :--- | :--- | :--- |
| SDD-CON-022 | ディスカバリー成果物のマスター配置先制約 | 検証済み（verified） |
| SDD-CON-032 | 設計成果物のマスター配置先およびID/Frontmatter制約 | 検証済み（verified） |
| SDD-CON-042 | データモデリングにおける Mermaid erDiagram 記述制約 | 検証済み（verified） |
| SDD-CON-043 | 製品非依存の論理データモデル先行設計制約 | 検証済み（verified） |
| SDD-CON-050 | 運用指標の階層別定義と根拠明示制約 | 検証済み（verified） |
| SDD-CON-052 | 運用設計成果物のマスター配置先およびID/Frontmatter制約 | 検証済み（verified） |
| SDD-FR-001 | spec_inspect のタスク ID 既知化（幽霊判定からの除外） | 検証済み（verified） |
| SDD-FR-010 | 構造検証スクリプトによる整合性検証とレポート出力 | 検証済み（verified） |
| SDD-FR-011 | 軽量レーン（ショートカット）の適用条件と制限 | 検証済み（verified） |
| SDD-FR-020 | 上流探索マスターファイルの同期展開 | 廃止（deprecated） |
| SDD-FR-021 | 仮説検証ゲート判定の記録 | 検証済み（verified） |
| SDD-FR-030 | ドメインストーリーの自動集約 | 廃止（deprecated） |
| SDD-FR-031 | API設計における下向き非循環依存と層規制 | 検証済み（verified） |
| SDD-FR-033 | 設計手法プロバイダによる代替可能性 (graceful degradation) | 検証済み（verified） |
| SDD-FR-040 | 論理データモデル仕様の同期展開 | 廃止（deprecated） |
| SDD-FR-041 | 物理格納設計仕様の同期対象外化 | 検証済み（verified） |
| SDD-FR-051 | 可観測性設計におけるアラートおよびランブック定義 | 検証済み（verified） |
| SDD-FR-053 | バックアップリストア検証およびDR試験の定義 | 検証済み（verified） |
| SDD-FR-060 | 統合報告書への decision キー必須出力 | 検証済み（verified） |
| SDD-FR-061 | Consistency 観点の指摘事項のプレフィックス分離 | 検証済み（verified） |
| SDD-FR-070 | タスク分解時のトレーサビリティ・境界の宣言 | 検証済み（verified） |
| SDD-FR-071 | タスクの並列投入条件の厳守 | 検証済み（verified） |
| SDD-FR-080 | 複数エージェント並列開発時の worktree 隔離 | 検証済み（verified） |
| SDD-FR-081 | 実装コミットの Implements フッター宣言 | 検証済み（verified） |
| SDD-FR-082 | タスク失敗時の worktree 破棄による復元 | 検証済み（verified） |
| SDD-FR-090 | テスト実装時の ID 付与と境界内配置 | 検証済み（verified） |
| SDD-FR-091 | テスト仕様書の定型記録 | 検証済み（verified） |
| SDD-FR-100 | 双方向同期コマンドにおける mtime 比較による上書き制御 | 検証済み（verified） |
| SDD-FR-101 | 個別ストーリーファイルからストーリードキュメントへの Pull 集約 | 廃止（deprecated） |
| SDD-FR-110 | 開発進捗・品質レポートの自動生成と出力 | 検証済み（verified） |
| SDD-FR-111 | 統合レポートにおける集計対象ステータスと構成 | 検証済み（verified） |
| SDD-FR-112 | 共有スクリプト変更時の全テストスイート実行と環境固有前提のスキップ扱い | 検証済み（verified） |
| SDD-FR-120 | sdd-plan スキルによる現状把握と次アクション提案 | 検証済み（verified） |
| SDD-FR-121 | sdd-issue スキルによる要望インテークと予備判定付き起票 | 検証済み（verified） |
| SDD-FR-122 | accepted spec-issue 着手時の起票時前提再検証 | 検証済み（verified） |
| SDD-FR-123 | 軽量レーンの検証証跡基準 | 検証済み（verified） |
| SDD-FR-124 | unit-test 検証手段の統制語彙追加 | 検証済み（verified） |
| SDD-FR-125 | 日本語6章文書構成と宣言式拡張 | 検証済み（verified） |
| SDD-FR-126 | 日本語章へのDiscovery同期 | 検証済み（verified） |
| SDD-FR-127 | 日本語章へのドメインストーリー集約 | 検証済み（verified） |
| SDD-FR-128 | 日本語章への設計・データ同期 | 検証済み（verified） |
| SDD-FR-129 | 旧8章から日本語6章への安全な移行 | 検証済み（verified） |
| SDD-FR-130 | sdd-doctor 環境診断スキル | 検証済み（verified） |
| SDD-FR-131 | spec-issue の accepted→rejected 再裁定遷移 | 検証済み（verified） |
| SDD-FR-132 | ワークスペース間 spec-issue 委託フローの正式化と機械検証 | 検証済み（verified） |
| SDD-FR-133 | spec_inspectの読み取り専用check-onlyモード | 検証済み（verified） |
| SDD-FR-134 | approved要件の孤児判定を警告へ分離 | 検証済み（verified） |
| SDD-FR-135 | frontmatter境界を保持する本文双方向同期 | 検証済み（verified） |
| SDD-FR-136 | spec_status のフェーズ語彙の正規化と設計フェーズの追加 | 検証済み（verified） |
| SDD-FR-137 | ライフサイクル語彙の対訳辞書と表示層の日本語化 | 検証済み（verified） |
| SDD-FR-138 | spec_update.py の日本語ラベル入力の正規化 | 検証済み（verified） |
| SDD-FR-139 | sdd_report のタスク集計を正規語彙へ整合し日本語表示する | 検証済み（verified） |
| SDD-FR-140 | フェーズ正規語彙のコード⇔文書一致を機械検証する | 検証済み（verified） |
| SDD-FR-141 | spec_status の委譲済み accepted spec-issue を未着手から分離集計する | 検証済み（verified） |
| SDD-FR-142 | spec_status による実施記録欠落の機械警告 | 検証済み（verified） |

---

## 3. 設計確立状況 (.spec/design/)
*   **ドメインモデル (domain-model.md)**: 未作成
*   **API設計 (api-design.md)**: 未作成
*   **アーキテクチャ設計 (architecture.md)**: 未作成

---

## 4. レビュー状況 (.spec/reviews/)
*   **統合ステータス**: 3 件のレビューが存在
*   **判定結果**: PASS (合格)

### レビュー報告書一覧
| ファイル名 | レビュー判定 |
| :--- | :--- |
| SDD-REV-003.md | `PASS` |
| review-synthesis.md | `PASS` |
| SDD-REV-002.md | `PASS` |

---

## 5. タスク実行状況 (.spec/tasks/ - 27 件)
*   **着手待ち（pending）**: 0 件
*   **実装中（implementing）**: 0 件
*   **介入待ち（blocked）**: 0 件
*   **完了（done）**: 27 件
