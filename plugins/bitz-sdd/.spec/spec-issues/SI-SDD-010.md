---
id: SI-SDD-010
raised_by: 4プラグインの Discovery docs 同期（2026-07-18）
target: sdd-docs の sdd_sync.py pull と docs_inspect.py の frontmatter 契約不整合
proposed_change_type: modify
status: accepted
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
- **依存**: SI-SDD-012（同期先となる日本語6章構成と移行方針を先に裁定する）。
  本issueは SI-SDD-011 の前提。
- **予備判定（推薦）**: **accept 推奨**。既存要件の raw copy と docs 検証契約が実地で矛盾しており、
  4ワークスペースの正規同期を阻害する。通常フロー + Design Gate で契約を改訂する。
- **裁定（2026-07-19, 人間）**: **accept**。frontmatter の機械契約を緩和せず、
  pull / push とも同期先固有の frontmatter を保持して本文だけを双方向同期する案で進める。
  新規 docs 同期先の frontmatter は同梱テンプレートから決定的に生成し、同期元の追跡は
  `DEFAULT_MAPPING` を正として、新しい docs frontmatter キーは追加しない。
- **着手時前提再検証（2026-07-19）**: SI-SDD-012 は SDD-FR-125〜129 として実施済み。
  起票時に改訂候補だった SDD-FR-020 は SDD-FR-126 に supersede されているため、
  本件は新規 SDD-FR-135 で frontmatter 境界を追加し、現行 SDD-FR-126 / 128 の日本語パスと
  SDD-FR-100 の mtime 保護を維持する。現行実装の `shutil.copy2` と内容完全一致テストにより、
  `pull → docs_inspect.py --strict` が5件の frontmatter ERROR になることを再現確認した。
- **実施**: 2026-07-19 SDD-FR-135をverified化。pull / pushを本文同期へ変更し、同期先固有の
  frontmatter保持、新規docsテンプレート生成、MASTER整合、異常入力拒否、原子置換、mtime同値化を実装した。
  対象24件・全263件green、docs strict・skill-validator・spec inspect・release_check PASSを確認した。
