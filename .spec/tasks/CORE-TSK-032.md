---
implements: CORE-CON-013
depends_on: []
boundary: AGENTS.md, tests/test_cli_contract.py
status: done
---

### ラッパーの公開ツール一覧と AGENTS.md の一致を機械検証する

- **作業内容**: AGENTS.md の SDD ツール実行節へ機械検証用マーカー
  `<!-- spec-wrapper-tools: ... -->` を追加し、`tests/test_cli_contract.py` で
  `scripts/spec` の `TOOLS` のキー集合との一致を検査する（`release_check.py` の
  フェーズ語彙マーカーと同型）。ラッパーを import せずソースから `TOOLS` を抽出する。
  マーカーだけ直して散文リストが取り残されるのを防ぐため、直前行の散文リストとの一致も
  検査する。あわせて直接実行するツール（`sdd_sync` / `docs_inspect` / `sdd_report` /
  `spec_verify`）がラッパーのサブコマンドに混ざっていないことを検査し、境界の二重定義を防ぐ。
  `scripts/spec` が無いリポジトリでは検査をスキップする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
