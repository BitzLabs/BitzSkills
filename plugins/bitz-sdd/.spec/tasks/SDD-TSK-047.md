---
implements: SDD-FR-158
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, skills/sdd-review/references/synthesis.md, skills/sdd-review/SKILL.md, tests/test_spec_inspect.py
status: done
---

### ReviewFinding の schema を固定し finding ID を横断一意にする

- **作業内容**: `spec_inspect.py` に `findings[]` の schema 検査を追加する。必須キーは
  `id` / `priority` / `severity` / `source` / `title` / `recommendation` / `tracked_by` /
  `status` の8つ（`tracked_by` はキーの存在のみ必須で、P2/P3 は空でよい）。finding ID は
  `<REV-ID>:SYN-NNN` 形式でレビュー横断に一意化し、`priority` / `severity` / `status` は
  統制語彙に限定する。**`schema_version` を持つ synthesis だけを検査対象**とし、既存レビューは
  遡及的に不整合としない。`sdd-review` の `references/synthesis.md` に schema の正を書き、
  `SKILL.md` の実行手順と ID 体系を更新する。`verdict` の算出式には触れない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
