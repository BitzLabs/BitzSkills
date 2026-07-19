---
implements: [SDD-FR-133, SDD-FR-134]
depends_on: []
boundary: plugins/bitz-sdd/.spec/, plugins/bitz-sdd/skills/sdd-core/, plugins/bitz-sdd/skills/sdd-implement/SKILL.md, plugins/bitz-sdd/skills/sdd-git/SKILL.md, tests/test_spec_inspect.py, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json, .claude-plugin/marketplace.json
status: done
---

### spec_inspectの並列開発向け検査契約を実装

- **作業内容**: テスト先行で次を実装する。
  1. `--check-only` 指定時に標準出力と終了コードを維持したまま、全ワークスペースの
     `inspection-report.md` を生成・更新しない回帰テストを追加する。
  2. approved要件のタスク未紐付けを実装待ちWARNへ分離し、implementing以降だけを
     孤児FAILとする回帰テストを追加する。
  3. `spec_inspect.py` のCLI・レポート生成・孤児判定を最小変更で実装する。
  4. sdd-core / sdd-implement / sdd-git の実行規定を新しい並列検査契約へ更新する。
  5. 変更した各SKILL.mdとbitz-sddプラグインのversionをsemverで更新する。
  6. 対象テスト、全pytest、canonical spec inspect、release_checkを実行する。
- **実施記録**: 2026-07-19 実施。対象7件・全254件green、ローカル2.4.0の
  check-only一括検査とcanonical検査・release_checkがPASS。bitz-sddは2.4.0へ更新。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
