# japanese-guard（取り込んだhook）

Claude Codeの応答が英語に切り替わったときに、日本語で書き直させるhookである。`.claude/settings.json`の`hooks.Stop`と
`hooks.PreToolUse`（matcher `mcp__.*__wrap_up`）から呼ぶ。

| 項目 | 内容 |
|---|---|
| 出どころ | https://github.com/minorun365/claude-code-japanese-guard |
| 取り込んだコミット | `4434ef4`（2026-11-28に取得） |
| 取り込んだファイル | `hooks/japanese-guard.py`、`LICENSE`、`NOTICE`。中身は変えていない |
| ライセンス | Apache License 2.0（`LICENSE`、`NOTICE`） |

- 標準ライブラリだけで動き、ネットワークへ接続せず、ファイルへ書き込まない（取り込む前に全体を読んで確かめた）。
- 無効にするときは、環境変数`JAPANESE_GUARD_DISABLE=1`を設定する。判定の閾値などの環境変数は、出どころのREADMEに従う。
- 更新するときは、出どころの新しいコミットの差分を読んでから、このディレクトリのファイルを置き換え、上の表のコミットを改める。
