---
implements: CORE-FR-018
depends_on: []
boundary: scripts/bump_version.py, tests/test_bump_version.py, AGENTS.md（定型手順節）
status: done
---

### bump_version.py をargparse化し--dry-runを追加する

- **作業内容**: `scripts/bump_version.py` の手書き `sys.argv` 解析を `argparse` へ置き換える。
  未知引数は argparse の既定動作で拒否され、`-h` / `--help` は引数位置に関わらず効くようになる。
  あわせて `--dry-run` を追加し、新旧 version を出力してマニフェストを書き換えずに終了する
  経路を用意する。既存の呼び出し形（`<plugin名>` 単独 = patch、`<plugin名> major|minor|patch`）は
  挙動を変えない。`tests/test_bump_version.py` を新規作成し、未知引数・位置違いの `--help`・
  `--dry-run`・後方互換の各ケースで終了コードと3マニフェストの before/after を検証する。
  AGENTS.md の「定型手順」節へ `--dry-run` を案内として追記する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
