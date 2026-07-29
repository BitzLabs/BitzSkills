---
implements: CORE-CON-011
depends_on: []
boundary: scripts/release_check.py, tests/test_cli_contract.py, AGENTS.md（規約節）
status: done
---

### CLIスクリプトの未知引数拒否を契約化し回帰テストで担保する

- **作業内容**: `scripts/release_check.py` に `argparse` を導入し、引数を取らない CLI として
  未知引数を拒否する（現状は `--bogus-flag` を黙認して PASS で終了する）。
  `tests/test_cli_contract.py` を新規作成し、`scripts/*.py`・`plugins/*/scripts/*.py`・
  `plugins/*/skills/*/scripts/*.py` から CLI スクリプトを実行時に収集して、
  各々へ解釈できない引数を渡すと非ゼロ終了すること、`--help` が副作用なく効くことを検証する。
  除外は stdin 駆動 hook（`agy_guard.py` / `env_guard.py`）、`__main__` を持たないライブラリ、
  ディスパッチャ `scripts/spec` に限り、除外理由をテスト内へ明記する。収集結果が空でないことも
  検証して収集漏れによる素通りを防ぐ。実行は一時ディレクトリを作業ディレクトリとして行う。
  あわせて AGENTS.md の規約節へ本契約の1行を追記し、`CORE-FR-018` の説明文にある
  「全スクリプトへの共通契約化は未着手」の記述を改訂する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
