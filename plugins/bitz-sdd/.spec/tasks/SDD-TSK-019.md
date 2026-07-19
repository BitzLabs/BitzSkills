---
implements: SDD-FR-135
depends_on: []
boundary: plugins/bitz-sdd/.spec/, plugins/bitz-sdd/skills/sdd-docs/scripts/sdd_sync.py, plugins/bitz-sdd/skills/sdd-docs/SKILL.md, tests/test_sdd_sync.py, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### frontmatter境界を保持する本文双方向同期を実装

- **作業内容**:
  1. SDD-FR-135のEARS節からpull/pushの正常系・異常系・mtime・strict回帰テストを先行追加する。
  2. テストが現行raw copy実装でredになることを確認する。
  3. `sdd_sync.py`へfrontmatter/本文分離、テンプレート生成、MASTER project_type整合、
     ファイル単位原子置換、mtime同値化、失敗集計と非0終了を実装する。
  4. sdd-docs SKILL.mdへ本文同期契約、push先欠如時のエラー、部分成功時の再実行を記載する。
  5. テスト仕様と検証結果を`.spec/specs/`へ記録する。
  6. sdd-docsスキルとbitz-sddプラグインをsemverで更新する。
  7. 対象テスト、全pytest、canonical spec inspect、release_checkを実行する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
- **実装結果**:
  - pull / pushをfrontmatterと本文に分離し、同期先frontmatterを保持して本文だけを同期した。
  - 新規docsは同梱テンプレートから生成し、`project_type`をMASTERへ正規化した。
  - 不正frontmatter・push先欠如を変更前に拒否し、部分失敗を集計して非0終了と再実行案内を返すようにした。
  - 同一ディレクトリ一時ファイルからの原子置換と同期元mtimeへの同値化を実装した。
  - sdd-docsを1.1.0、bitz-sddを2.5.0へ更新した。
- **検証結果**: RED 18 failed / 6 passedから、対象24 passed・全体263 passedへ改善。
  skill-validator、docs strict、local check-only、canonical spec inspect、release_checkはいずれもPASS。
