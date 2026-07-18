---
implements: CORE-CON-008
depends_on: []
boundary: plugins/bitz-env/skills/env-destroy/, plugins/bitz-env/skills/env-doctor/, plugins/bitz-env/skills/env-init/SKILL.md, plugins/bitz-env/README.md, plugins/bitz-env/.claude-plugin/plugin.json, plugins/bitz-env/plugin.json, plugins/bitz-env/.codex-plugin/plugin.json, plugins/bitz-env/.spec/requirements/ENV-FR-010.md, plugins/bitz-env/.spec/design/ENV-DSN-001.md, plugins/bitz-env/.spec/specs/bitz-env/test-spec.md, evals/env-destroy/
status: done
---

### env-destroy を env-uninstall へ改名（CORE-CON-008 標準命名への追随）

- **作業内容**: `plugins/bitz-env/skills/env-destroy/` を `plugins/bitz-env/skills/env-uninstall/`
  へリネームする。SKILL.md の name フィールド・本文中の自己言及、env-init 等の他スキルからの参照、
  README.md の一覧表を更新する。ENV-FR-010（verified）・ENV-DSN-001（approved）・test-spec.md は
  改名後も現状を正しく記述する現行仕様として本文中の `env-destroy` 表記を更新する
  （挙動は変わらないため再検証・ステータス変更は不要。ENV-FR-010 は Revision History に改名を追記）。
  過去の裁定記録（spec-issues / discovery / review / 完了済みタスク・test-spec 検証ステータス欄の
  日付付き記述）と `evals/env-destroy/`（AGENTS.md ガードレールにより evals/ 配下の改名は
  事前確認が必要なため対象外。ENV-FR-010 の検証手段はディレクトリ名を据え置きのまま参照）は
  書き換えない。`grep -rln "env-destroy" plugins/bitz-env evals/` の残存が上記の意図的な
  非対象ファイルのみであることを確認した（確認済み）。最後に bitz-env のバージョンを
  `scripts/bump_version.py bitz-env minor` で bump する（スキル名変更のため minor）。
- **実施記録**: 2026-07-18 実施。release_check PASS・spec_inspect --workspace . plugins/* 全6ワークスペース PASS。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
