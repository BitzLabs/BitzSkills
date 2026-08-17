---
implements: SDD-FR-146
depends_on: []
boundary: skills/sdd-core/SKILL.md, skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py, .claude-plugin/plugin.json, .codex-plugin/plugin.json, plugin.json, .spec/spec-issues/SI-SDD-043.md
status: done
---

### クロスワークスペース参照識別子を安定化する

- **作業内容**: `external_refs_for()` が生成する参照元ラベルを、Git リポジトリ内では
  top-level からの相対パス（ルートは `.`）へ正規化する。Git が使えない場合や
  ワークスペースがリポジトリ外にある場合は従来の basename 表記へ縮退する。
  異なるディレクトリ名の checkout でも同一レポートになる回帰テスト、サブワークスペースの
  `plugins/<name>` 表記、Git 非利用時の後方互換、単一ワークスペース非退行を検証する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
