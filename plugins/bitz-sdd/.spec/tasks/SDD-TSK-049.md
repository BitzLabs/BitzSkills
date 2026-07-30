---
implements: SDD-FR-160
depends_on: []
boundary: .spec/reviews/, skills/sdd-core/scripts/spec_inspect.py, skills/sdd-core/assets/artifact-frontmatter.md, skills/sdd-review/references/synthesis.md, skills/sdd-report/scripts/sdd_report.py, tests/test_spec_inspect.py
status: done
---

### review-synthesis をビュー化しレビューのアーカイブを強制する

- **作業内容**: `review-synthesis.json` / `.md` を最新へのビューへ格下げし、成果物の正を
  番号付きの `<REV-ID>.json` / `.md` にする。`load_requirements` は `review-synthesis.md` を
  レジストリから除外する（自前の ID を持たないため。これを先にやらないと番号付きへ複写した
  瞬間に既存の重複 ID 検査が発火して FAIL する）。`spec_inspect` にアーカイブ漏れ検査
  （ビューの `review_id` に対応する番号付きファイルの不在）と `carried_over[]` の取り込み元
  実在検査を追加する。アーカイブ漏れは `schema_version` の有無にかかわらず適用する。
  実データの移行として bitz-sdd と他4ワークスペース（ルート / bitz-ddd / bitz-env /
  bitz-flow）の未アーカイブなレビューを番号付きへ退避する。Markdown 側のビューは `_` 始まりの
  `_review-synthesis.md` として置き、**固定版として古い bitz-sdd を消費しているワークスペースでも
  「id が無い」FAIL を起こさない**ようにする。`sdd_report` のレビュー集計も `_` 始まりを除外する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
