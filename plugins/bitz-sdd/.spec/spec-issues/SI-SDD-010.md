---
id: SI-SDD-010
raised_by: 4プラグインの Discovery docs 同期（2026-07-18）
target: sdd-docs の sdd_sync.py pull と docs_inspect.py の frontmatter 契約不整合
proposed_change_type: modify
status: open
---
- **目的**: `sdd_sync.py pull` が `.spec/discovery/*.md` を frontmatter ごと `docs/` へコピーする一方、
  `docs_inspect.py` は docs 文書に `DOC-*` ID、`proposed|active` status、semver、`changeImpact`、
  `project_type` を必須とする。同じ sdd-docs スキルが要求する「pull 後に docs_inspect 0件」を
  現行実装では同時に満たせないため、同期契約を一貫させる。
- **提案する修正**:
  1. pull を raw copy から docs frontmatter を保持・生成する決定的レンダリングへ変更し、本文だけを
     `.spec` から同期する。同期元は `derived_from` 等で追跡する
  2. push は docs 固有 frontmatter を `.spec` へ逆流させず、本文または明示マッピングだけを反映する
  3. SDD-FR-020 / SDD-FR-100 の「コピー」契約を、docs frontmatter 契約と両立する同期へ改訂する
  4. pull → `docs_inspect.py --strict` が0件になる回帰テストを先行追加する
- **対象ファイル**: `skills/sdd-docs/scripts/sdd_sync.py`、`docs_inspect.py`、`tests/test_sdd_sync.py`、
  `skills/sdd-docs/SKILL.md`、SDD-FR-020 / SDD-FR-100 の後継または改訂要件、bitz-sdd マニフェスト。
- **確認観点**: Discovery の `DSC-*` と Design の `DSN-*` を pull しても docs 側は `DOC-*` 契約で
  strict PASS すること。mtime による新旧判定、既存 docs の手動本文、push の方向性を壊さないこと。
- **影響推定・ロールバック**: 公開同期API・frontmatter契約に触れるため軽量レーン不可。
  `--impact SDD-FR-020` では既存依存タスク `SDD-TSK-002` 1件。新レンダラと要件を一括 revert 可能。
- **依存**: なし。SI-SDD-011 の前提。
- **予備判定（推薦）**: **accept 推奨**。既存要件の raw copy と docs 検証契約が実地で矛盾しており、
  4ワークスペースの正規同期を阻害する。通常フロー + Design Gate で契約を改訂する。
