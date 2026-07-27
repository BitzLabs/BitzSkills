---
id: CORE-TSK-027
implements: CORE-FR-017
depends_on: [CORE-TSK-026]
boundary: plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py, tests/test_docs_inspect.py
status: done
---

### CORE-TSK-027 docs_inspect.py の除外判定ロジック強化とテスト更新

- **作業内容**:
  `docs_inspect.py` の `collect_docs` 関数において、ディレクトリだけでなく個別ファイル単位の `excluded_paths` もスキップされるよう判定を強化する。また `tests/test_docs_inspect.py` に除外指定パスのテストケースを追加・更新する。
- **完了条件**:
  - `excluded_paths` に指定されたフォルダ・ファイルが `collect_docs` およびレジストリチェックで除外されること。
  - `tests/test_docs_inspect.py` のテストが PASS すること。
