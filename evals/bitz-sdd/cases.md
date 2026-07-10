# bitz-sdd テストケース（Phase 5b: MVC + Database 一気通貫検証）

対象: bitz-sdd プラグイン v1.2.0 のワークフロー全体
（discovery → design → data → ops → review → report）。
題材はマスタープラン Phase 5b の指定どおり「ToDo アプリ（MVC + Database 構成）」。

## TC-01: MVC + DB 題材の一気通貫設計（スキルあり/なし比較）
- **種別**: 正常系
- **入力プロンプト**: 個人用の ToDo 管理 Web アプリを作りたい。画面（一覧・追加・完了）、サーバー、データベースがある普通の MVC 構成。仕様駆動で設計を一通り進めて。
- **前提条件**: 空のプロジェクトディレクトリ。bitz-ddd プラグインは**未導入**（graceful degradation の検証を兼ねる）
- **アサーション**:
  - [ ] `.spec/discovery/` に上流探索の成果物（vision / scope 相当）が作成されている
  - [ ] `.spec/design/domain-model.md` が作成されている（bitz-ddd なしでも軽量ドメインスケッチとして成立）
  - [ ] `.spec/design/data-model.md` が作成され、ER 図（Mermaid erDiagram）と格納方式選定（RDB 採用の証拠駆動の根拠）を含む
  - [ ] `.spec/design/architecture.md` にレイヤリング（MVC とデータ層の対応）の記述がある
  - [ ] `.spec/reviews/` にレビュー結果（判定付き）が作成されている
  - [ ] `sdd_report.py` の実行で `.spec/reports/status-report.md` が生成される
  - [ ] `sdd_sync.py pull` の実行で `docs/02-design/data-model.md` へ同期される
  - [ ] フローが bitz-ddd 未導入のまま最後（report）まで完走している
- **期待成果物**: サンドボックスプロジェクトの `.spec/` ツリー一式 + `docs/02-design/`

## TC-02: sdd-data の発動判定
- **種別**: 発動判定
- **入力プロンプト**: （a）「タスクの保存先を SQLite にするか JSON ファイルにするか決めたい」（b）「テーブル設計をレビューして」（c）「標準入力を整形して標準出力に出すだけの CLI フィルタを設計して。状態は持たない」（d）「UI の配色を決めたい」
- **前提条件**: なし（description のみで判定。本文は見ない）
- **アサーション**:
  - [ ] (a) に対して sdd-data を使うと判断する（格納方式の選定は守備範囲）
  - [ ] (b) に対して sdd-data を使うと判断する（スキーマ設計は守備範囲）
  - [ ] (c) に対して sdd-data を使わないと判断する（永続データなし）
  - [ ] (d) に対して sdd-data を使わないと判断する（データ格納と無関係）

## TC-03: DB を使わないシステムでの工程スキップ（エッジケース）
- **種別**: エッジケース
- **入力プロンプト**: 電卓 CLI ツール（履歴保存なし・完全ステートレス）を仕様駆動で設計して。
- **前提条件**: 空のプロジェクトディレクトリ
- **アサーション**:
  - [ ] 設計工程で sdd-data が必須ステップとして強制されない（スキップの判断が明示される）
  - [ ] `.spec/design/data-model.md` を無理に作成しない
  - [ ] design → review の流れ自体は成立する
