# 8. トラブルシューティング (Troubleshooting)

OpenAI Codex 運用時に遭遇しやすい問題と対処をまとめます。

---

## 8.1 Linux / WSL2 でのサンドボックス起動失敗

`bwrap`（bubblewrap）が未インストール、または AppArmor の unprivileged user namespace 制限で `bwrap` が名前空間を作れない場合に警告が出ます。Ubuntu 24.04 では `apt install apparmor-profiles apparmor-utils` の上で `bwrap-userns-restrict` プロファイルをロードするか、`sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` が必要です（後者は制限緩和のため要検討）。

---

## 8.2 承認プロンプトでのハング

非対話実行（CI 等）で `approval_policy` を明示せず承認待ちが発生してプロセスが停止するケースは、`--ask-for-approval never` または `--sandbox workspace-write`（必要なら `--add-dir`）を明示することで回避します。granular approval の各サブフラグ（`mcp_elicitations` 等）を `false` のまま放置すると、該当種別の要求が自動拒否（fail closed）される点にも注意します。

---

## 8.3 ネットワークアクセス不可

`features.network_proxy.domains` を未設定のまま `workspace-write` で動かすと、外部宛先は既定で全て拒否されます。npm インストール等が失敗する場合は、まず対象ドメインの `allow` ルール追加を確認します。

---

## 8.4 Hooks が動かない

次の4点を順に確認します。(a) `features.hooks`（または `codex_hooks`）が有効か。(b) `hooks.json` の配置場所（`~/.codex/hooks.json` または `<repo>/.codex/hooks.json`）が正しいか。(c) **Windows では現状 Hooks 自体が無効**。(d) `PreToolUse` / `PostToolUse` は現状 Bash ツール以外を捕捉しない仕様上の制約。

---

## 8.5 認証まわり

`codex login`（ブラウザ OAuth）と `codex login --with-api-key`（stdin 経由 API キー、例 `printenv OPENAI_API_KEY | codex login --with-api-key`）の2系統があります。`codex login status` が終了コード 0 を返すかで、自動化スクリプト内の認証確認が可能です。`cli_auth_credentials_store`（`file` / `keyring` / `auto`）でファイル保存か OS キーチェーン保存かを選べます。

---

## 8.6 MCP サーバー接続タイムアウト

既定は起動10秒・ツール実行60秒です。重い MCP サーバでは `mcp_servers.<id>.startup_timeout_sec` / `tool_timeout_sec` を延長します。
