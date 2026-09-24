# bitz-core

Bitz Core 1.0 のCLI実装（`bitz` コマンド）。`context` / `check` / `verify` / `doctor` の4操作を提供する。

- source tree: `src/bitz/`（配布物名・import package名・CLI実行体名はすべて `bitz`）
- runtime依存: `ruamel.yaml==0.19.1`（YAML 1.2部分集合を安全に解析するためのexact pin）
- 実行: `uv run --project . bitz <operation> [...]`
- 試験: `tests/bitz-core/`（このディレクトリの外。ADR-049）

詳細な規範は `docs/03.詳細設計/` を正とする。
