---
id: CORE-FR-011
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-022（検証ツール実行パスの摩擦解消。SI-CORE-021 振り返り由来）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-011 scripts/spec ラッパーによる SDD ツールのバージョン非依存解決

- **説明**: 本リポジトリは bitz-sdd を「インストール済みプラグイン」として消費（ドッグフーディング）する
  ため、SDD ツール（spec_inspect / spec_scaffold / spec_status / spec_update）の実体はリポジトリの
  `scripts/` ではなくプラグインキャッシュ側にあり、案内どおり `python3 scripts/<tool>.py` では実行できない。
  毎回バージョン込みの絶対パスをハードコードする摩擦（SI-CORE-022）を解消するため、バージョン番号を
  直書きせずインストール記録の固定版を優先解決し当該ツールへ委譲するラッパー `scripts/spec` を提供する。
- **受入基準 (EARS)**:
  - WHEN 既知ツール名（inspect/scaffold/status/update）と引数で実行する THEN `installed_plugins.json` の projectPath がリポジトリルートに一致する bitz-sdd の installPath 配下の当該スクリプトへ委譲し引数と終了コードを透過すること SHALL
  - WHERE `installed_plugins.json` に該当エントリが無い THEN プラグインキャッシュ配下で当該ツールを備える semver 最大バージョンへフォールバックすること SHALL
  - THEN ラッパーはバージョン番号を直書きせずメタデータ/semver で解決すること SHALL
  - WHEN 未知のツール名を指定する THEN 非ゼロで失敗し有効なツール名を提示すること SHALL
  - WHERE 解決先スクリプトが存在しない THEN 非ゼロで失敗し理由を示すこと SHALL
- **検証手段**: tests/test_spec_wrapper.py（テスト先行）。環境変数 `BITZSKILLS_PLUGINS_DIR` でプラグイン
  格納先を差し替え、固定版の優先解決・キャッシュ最新フォールバック（ツール欠落版のスキップ）・
  引数/終了コードの透過・未知ツール/解決不能時の非ゼロ失敗・バージョン直書き禁止を example-test で検証する。
- **Revision History**:
  - 1.0 (2026-07-15) 初版（draft 起票。SI-CORE-022 の要件化）
