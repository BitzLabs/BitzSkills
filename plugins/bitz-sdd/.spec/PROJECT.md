# bitz-sdd ワークスペース

bitz-sdd プラグイン（仕様駆動開発ワークフロー）自身の SDD ワークスペース。モノレポ運用
（sdd-core の Monorepo & Workspaces 節）に従う個別ワークスペースであり、
リポジトリ共通規約はルート `.spec/`（CORE-）が持つ。

- ID プレフィックス: `SDD-`（例: `SDD-FR-001`）。逆起票分はスキルごとに番号ブロックを
  割当（010=core / 020=discovery / 030=design / 040=data / 050=ops / 060=review /
  070=implement / 080=git / 090=test / 100=docs / 110=report。FR/NFR/CON でブロック共有）
- 検証: `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py plugins/bitz-sdd`
  （クロスリファレンス解決は `--workspace . plugins/*`）
- テスト: ルート `tests/test_spec_inspect.py` / `tests/test_frontmatter_parsers.py`
  （同梱スクリプトの契約 unit-test）

## 経緯（ブラウンフィールド開始）

v1.4.5 時点で 11 スキルが実装・リリース済み。本ワークスペースはその実装へ仕様を
追いつかせる reverse-derived で開始している（origin に明記）。
以後の変更は通常の SDD フロー（要件 → タスク → 実装 → 検証）で行う。

### ブートストラップ対策

ルート `.spec/PROJECT.md` の規定と同じく、bitz-sdd 自身の開発に適用する bitz-sdd は
**リリース済み（main にマージ済み）バージョンに固定**する。開発中の作業ツリー版スキルを
自分自身の開発プロセスへ適用しない。

## 系譜（ルート CORE- からの引き継ぎ）

本ワークスペース新設（2026-07-12）以前の bitz-sdd 対象の修正はルート `.spec/` で
追跡された。以下は**ルートに履歴として残し、移設しない**:

- SI-CORE-001 → CORE-FR-001 → CORE-TSK-001（sdd-design 成果物表の必須/任意明示）— verified/done
- SI-CORE-002 → CORE-FR-002 → CORE-TSK-003（spec_inspect の自己言及 ID 除外）— verified/done
- SI-CORE-003（spec_inspect のタスク ID 既知化）— 実装済み。要件化は本ワークスペースの
  SDD-FR-001 が引き継ぐ

以後の bitz-sdd 変更はすべて SDD- 名前空間で起票する。

## 公開契約（軽量レーン禁止・Design Gate 対象）

- 成果物 frontmatter 書式: `skills/sdd-core/references/artifact-frontmatter.md`
- EARS 記法（受入基準の節種別とテスト導出パターン）
- spec_inspect.py の CLI と判定仕様（幽霊参照・孤児要件・カバレッジ・--workspace 解決）
- sdd_sync.py の pull / push 同期マッピング（docs/ ⇄ .spec/）
- .spec/ ディレクトリスキーマ（discovery / requirements / design / reviews / spec-issues / specs / tasks / reports）
- タスク分解の宣言項目: implements / depends_on / boundary（sdd-implement の task-decomposition.md）
