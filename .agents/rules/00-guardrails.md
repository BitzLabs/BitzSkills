# BitzSkills ガードレール（Antigravity 用）

- リポジトリ直下の `AGENTS.md`（特に「ガードレール」節）に必ず従うこと。
- `rm -rf` / `git push --force` / `git reset --hard` / `git clean -f` は実行しない。
- リポジトリ外への書き込み（`~/.claude/skills/` や `~/.gemini/config/skills/` への
  配置・上書き・削除）はユーザーの明示承認を得てから行う。
- 作業の完了を報告する前に `python3 scripts/release_check.py` を実行し、
  その実際の出力を根拠として示す。「成功したはず」という推定で報告しない。
