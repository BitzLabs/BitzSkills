---
id: CORE-FR-011
version: 1.1
status: verified
domain: tooling
priority: medium
origin: SI-CORE-022（初版）、SI-CORE-034（Claude/Codex横断解決への改版）
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
  毎回バージョン込みの絶対パスをハードコードする摩擦（SI-CORE-022）と、Claude用キャッシュしか
  解決できずCodexでは環境変数が必要になる摩擦（SI-CORE-034）を解消するため、バージョン番号を
  直書きせずClaude/Codexの有効な固定版を優先解決し当該ツールへ委譲するラッパー `scripts/spec` を提供する。
- **受入基準 (EARS)**:
  - WHEN 既知ツール名（inspect/scaffold/status/update）と引数で実行する THEN 解決した単一bitz-sdd版の当該スクリプトへ委譲し引数と終了コードを透過すること SHALL
  - WHERE `BITZSKILLS_PLUGINS_DIR` が指定される THEN 指定ルートだけを探索しCodex CLIや他ルートへfallbackしないこと SHALL
  - WHERE override未指定かつCodex CLIがinstalledかつenabledな `bitz-sdd@bitzskills` を返す THEN `CODEX_HOME` 配下の同一versionを固定版として検証・優先すること SHALL
  - WHERE Codex CLIがdisabled、uninstalledまたはno-entryを正常応答する THEN Codex cacheをfallback候補から除外すること SHALL
  - WHERE Codex CLIが不在、timeoutまたは非ゼロ終了で利用不能である THEN CodexとClaudeの既知cacheを検証付きfallback候補にすること SHALL
  - WHERE Claudeの `installed_plugins.json` にprojectPath一致エントリがある THEN installPathの同一versionを固定版として検証・優先すること SHALL
  - WHEN 複数固定版のversionが異なるか同一versionのfingerprintが異なる THEN 非ゼロで安全停止し明示overrideを案内すること SHALL
  - WHERE 固定版が無い THEN manifestと全4ツールが完全な厳格SemVer最大の単一plugin版へfallbackすること SHALL
  - WHERE 有効な固定版のmanifest、versionまたは全4ツールの検証に失敗する THEN 他版へfallbackせず非ゼロで安全停止すること SHALL
  - THEN ラッパーはバージョン番号を直書きせずメタデータ/semver で解決すること SHALL
  - WHEN 未知のツール名を指定する THEN 非ゼロで失敗し有効なツール名を提示すること SHALL
  - WHERE 解決不能、曖昧性または実行直前の候補変更を検出する THEN 探索ルート・安全な失敗分類・明示overrideまたは再試行の復旧方法を示して非ゼロで失敗すること SHALL
- **検証手段**: tests/test_spec_wrapper.py（テスト先行）。fixtureのClaude/Codex CLI JSON・cacheを使い、
  override、固定版、discovery状態別縮退、競合・破損時の安全停止、厳格SemVer、単一plugin版、
  引数/終了コード透過、診断情報をexample-testで検証する。
- **Revision History**:
  - 1.0 (2026-07-15) 初版（draft 起票。SI-CORE-022 の要件化）
  - 1.1 (2026-07-27) verified（対象pytest 25件・全pytest 328件・release_check・overrideなしCodex実地statusがgreen。全workspace inspectは既知baselineのみ残存）
