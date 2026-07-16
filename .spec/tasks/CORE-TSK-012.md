---
implements: CORE-FR-011
depends_on: []
boundary: scripts/spec, tests/test_spec_wrapper.py
status: done
---

### scripts/spec ラッパーの実装（CORE-FR-011）

- **作業内容**: バージョン非依存に SDD ツール（inspect/scaffold/status/update）を解決して委譲する
  ラッパー `scripts/spec` を実装する。`installed_plugins.json` の projectPath 一致エントリの
  固定版を優先解決し、無ければプラグインキャッシュの semver 最大版（ツール欠落版はスキップ）へ
  フォールバックする。未知ツール・解決不能・解決先スクリプト不在は非ゼロで失敗させる。
- **検証**: `tests/test_spec_wrapper.py`（テスト先行・example-test）。`BITZSKILLS_PLUGINS_DIR` で
  プラグイン格納先を差し替え、固定版優先・フォールバック・引数/終了コード透過・非ゼロ失敗・
  バージョン直書き禁止を確認する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
