---
id: CORE-TSK-028
implements: CORE-FR-017
depends_on: [CORE-TSK-026, CORE-TSK-027]
boundary: tests/
status: done
---

### CORE-TSK-028 docs_inspect 適用範囲の最終検証と回帰テスト確認

- **作業内容**:
  `docs_inspect.py` を実リポジトリルートに対して実行し、エラーが解消されることを確認する。あわせて全 pytest および `scripts/release_check.py` を実行して回帰がないことを確認する。
- **完了条件**:
  - `python3 plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py .` がエラーなし（または正常な検出のみ）で実行完了すること。
  - 全テスト・release_check が PASS すること。
