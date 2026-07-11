# bitz-env レジストリ

env-init / env-register が生成・変更した項目の記録。env-destroy はこの記録のみを
撤去対象の根拠とする。

## 生成日時: 2026-07-05T10:00:00+09:00（2026-07-12 部分撤去により更新）

### 新規生成したファイル

- ~~`.claude/agents/advisor.md`~~（2026-07-12 撤去済み）
- ~~`.claude/agents/worker.md`~~（2026-07-12 撤去済み）

### 既存ファイルへ書き込んだマーカー区間

- `AGENTS.md`（ガードレール節、`<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`）
  — ユーザーの指示によりこの区間のみ**残置**（部分撤去 2026-07-12）
- ~~`CLAUDE.md`（協調運用節）~~（2026-07-12 撤去済み）

### settings.json への書き込み

- ~~`.claude/settings.json` の permissions.deny に bitz-env 推奨 deny セット（9件）を追記~~
  （2026-07-12 撤去済み）

### バックアップの有無

- git 管理下のため `.bak` は作成していない

### 協調アダプタ登録（env-register）

- なし
