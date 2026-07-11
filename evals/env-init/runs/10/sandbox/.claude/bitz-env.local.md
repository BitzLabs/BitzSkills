# bitz-env レジストリ（env-init 生成物トラッキング）

- **生成日時**: 2026-07-12
- **プラットフォーム**: Claude Code
- **中心モデル**: Sonnet（中位、ユーザー選択）／ advisor: Opus ／ worker: Haiku

## 新規生成したファイル

- `.claude/agents/advisor.md`（model: opus）
- `.claude/agents/worker.md`（model: haiku）
- `.claude/bitz-env.local.md`（本ファイル）

## 既存ファイルへ書き込んだマーカー区間

- `AGENTS.md`（ガードレール節、`<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->`、既存10行の直後に追記）
- `CLAUDE.md`（協調運用節、`<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->`、既存5行の直後に追記）
- `.claude/settings.json`（permissions を和集合マージ。既存 deny "Bash(npm publish:*)" は保持、
  既存 ask "Bash(git push:*)" はテンプレートと同一のため重複なし）

## バックアップの有無

- git 管理下のため `.bak` は作成していない（git 自体を復旧手段とみなす）
