---
id: CORE-FR-010
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-SDD-003（scaffold 生成時語彙検証・DSN 種別。SI-CORE-021 振り返り由来）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-010 spec_scaffold.py の生成時語彙検証と DSN 種別の追加

- **説明**: `spec_scaffold.py`（CORE-FR-004）が frontmatter の統制語彙を生成時に検証しないため、
  語彙外の値が雛形に混入し、人間が approved 化した後に初めて `spec_inspect.py` が FAIL する。
  また設計ノート（DSN）には scaffold サブコマンドが無く手書きのため status 語彙外で FAIL していた。
  生成時に語彙を検証して誤りを早期（生成時）に fail させ、承認後の手戻りを防ぐ。あわせて DSN の
  scaffold 種別を新設し、手書き起因の frontmatter 誤りを構造的に防ぐ。
- **受入基準 (EARS)**:
  - WHEN requirement 種別を `--verification-method` 付きで生成する THEN 値が `spec_inspect.py` の `VMETHODS` 語彙に無ければ非ゼロで失敗し雛形を生成しないこと SHALL
  - WHEN requirement 種別を `--domain` 付きで生成し当該ワークスペースに `domains.md` が存在する THEN 値が `domains.md` の語彙に無ければ非ゼロで失敗し雛形を生成しないこと SHALL
  - WHERE 当該ワークスペースに `domains.md` が存在しない THEN domain 検証はスキップし従来どおり生成すること SHALL
  - WHEN 語彙内の正常な値で生成する THEN 従来どおり雛形を生成すること SHALL（後方互換）
  - THEN 語彙定義（`VMETHODS` / `STATUSES`）は `spec_inspect.py` と単一の正を共有し二重定義しないこと SHALL
  - WHEN `design` 種別（DSN）を生成する THEN 生成物は `id` と既定 `status: draft`（DSN 有効語彙 draft/in-review/active/revised/archived の一つ）を持ち `spec_inspect.py` の検証を PASS する書式互換であること SHALL
  - WHEN `design` 種別を `--status` 指定で生成する THEN 値が `spec_inspect.py` の `STATUSES` 語彙に無ければ非ゼロで失敗し雛形を生成しないこと SHALL
- **検証手段**: tests/test_spec_scaffold.py（テスト先行）。語彙外の `--verification-method` /
  `--domain` / `--status` で exit≠0・雛形非生成、正常語彙で従来どおり生成（後方互換）、DSN 生成物が
  spec_inspect PASS、語彙が spec_inspect と単一定義（二重管理でない）ことを example-test で検証する。
- **Revision History**:
  - 1.0 (2026-07-15) 初版（draft 起票。SI-SDD-003 の要件化）
