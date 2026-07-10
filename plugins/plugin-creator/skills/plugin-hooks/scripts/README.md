# フック開発ユーティリティスクリプト

デプロイ前にフック実装を検証・テスト・リントするためのスクリプト群。

## validate-hook-schema.sh

`hooks.json` の構造とよくある問題を検証する。

```bash
./validate-hook-schema.sh path/to/hooks.json
```

**検証項目**: JSON構文 / 必須フィールド / イベント名の妥当性 /
フック種別（command/prompt）/ timeout の範囲 / ハードコードパスの検出 /
プロンプトフックのイベント互換性。

## test-hook.sh

個々のフックスクリプトをサンプル入力でテストする。

```bash
# サンプル入力の生成
./test-hook.sh --create-sample PreToolUse > test-input.json

# フックのテスト
./test-hook.sh my-hook.sh test-input.json

# 詳細出力・タイムアウト指定
./test-hook.sh -v -t 30 my-hook.sh test-input.json
```

**機能**: 環境変数（CLAUDE_PROJECT_DIR / CLAUDE_PLUGIN_ROOT）のセットアップ、
実行時間の計測、出力JSONの検証、終了コードの解釈、環境ファイル出力の取得。

## hook-linter.sh

フックスクリプトのベストプラクティス違反をチェックする。

```bash
# 単一スクリプト
./hook-linter.sh ../examples/validate-write.sh

# 複数スクリプト
./hook-linter.sh ../examples/*.sh
```

**検査項目**: shebang / `set -euo pipefail` / stdin読み取り / エラー処理 /
変数クォート（インジェクション防止）/ 終了コード / ハードコードパス /
長時間実行コード / stderrへのエラー出力 / 入力検証。

## 典型的なワークフロー

1. フックスクリプトを書く
2. リント: `./hook-linter.sh my-plugin/scripts/my-hook.sh`
3. テスト入力を作る: `./test-hook.sh --create-sample PreToolUse > test-input.json`
4. テスト: `./test-hook.sh -v my-plugin/scripts/my-hook.sh test-input.json`
5. hooks.json に追加する
6. 設定を検証: `./validate-hook-schema.sh my-plugin/hooks/hooks.json`
7. Claude Code でテスト: `claude --debug`

## よくある問題

**フックが実行されない**: shebang の有無、実行権限（`chmod +x`）、
hooks.json のパス（`${CLAUDE_PLUGIN_ROOT}` を使う）を確認。

**タイムアウトする**: hooks.json の timeout を調整、スクリプトを最適化、
長時間処理を除去。

**静かに失敗する**: 終了コード（0 または 2）、エラーの stderr 出力（`>&2`）、
JSON出力の構造を確認。

**インジェクション脆弱性**: 変数を必ずクォート、`set -euo pipefail` を使用、
全入力を検証、リンタを実行。
