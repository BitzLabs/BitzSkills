---
implements: SDD-FR-162
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, tests/test_spec_inspect.py, tests/test_spec_scaffold.py
status: done
---

### 設計成果物の再帰走査と frontmatter 基準の採番を実装する

- **作業内容**:
  1. `spec_inspect.py` に走査対象の定数（`ARTIFACT_DIRS` / `RECURSIVE_ARTIFACT_DIRS` /
     `NON_ARTIFACT_NAMES`）と `iter_artifact_files()` を追加し、`load_requirements` の
     固定リスト非再帰 glob を置き換える。`design` 配下だけ再帰する。
  2. 重複 ID 検出時のメッセージへ、衝突した両成果物のワークスペース相対パスを含める。
  3. `spec_scaffold.py` の `next_number()` を frontmatter の `id:` 基準へ変更し、
     `id:` を持たない成果物はファイル名からの抽出へフォールバックする
     （説明的サフィックス付きの慣行を維持）。`recursive` 引数で走査範囲を
     `spec_inspect` と一致させる（走査対象の定数は `spec_inspect` から import し二重定義しない）。
  4. `tests/test_spec_inspect.py` / `tests/test_spec_scaffold.py` に回帰テストを追加。
  5. `sdd-core` SKILL.md のディレクトリ構成と採番の説明を追随させる。
- **検証**:
  - `pytest` 全スイート PASS。
  - `spec_inspect.py --workspace . plugins/*` が PASS（既存7ワークスペースを遡及 FAIL させない）。
  - 修正前スクリプト（`origin/main`）との比較で、同一 ID の2成果物が
    `design/` 直下と `design/stories/` に存在する状態が修正前は exit 0（無検出）、
    修正後は exit 1 かつ両パス報告になることを実測。
  - 同様に `domain-model.md`（`id: SDD-DSN-009`）と `stories/`（`id: SDD-DSN-007`）だけがある
    workspace で、修正前の採番が 001、修正後が 010 になることを実測。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
