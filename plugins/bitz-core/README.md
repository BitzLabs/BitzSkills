# bitz-core

Bitz Core 1.0 のCLI実装（`bitz` コマンド）。`context` / `check` / `verify` / `doctor` の4操作を提供する。

- source tree: `src/bitz/`（配布物名・import package名・CLI実行体名はすべて `bitz`）
- runtime依存: `ruamel.yaml==0.19.1`（YAML 1.2部分集合を安全に解析するためのexact pin）
- 実行: `uv run --project . bitz <operation> [...]`
- 試験: `tests/bitz-core/`（このディレクトリの外。ADR-049）

詳細な規範は `docs/03.詳細設計/` を正とする。

## 日本語Coreスキル

[`skills/bitz-core/SKILL.md`](skills/bitz-core/SKILL.md)は、4操作の選択、入力の確認、
安全な実行、公開結果の説明を担当する。操作・結果・安全の参照を必要な場面で読む。
スキルはプラグインの`skills/`から発見する。CLI実行体の導入は別途必要であり、
スキルの読込みだけでPython環境や依存をインストールしない。

対応範囲はCore 1.0、公開API 1.x、Linux／macOS、CPython 3.12以上。
仕様の構文、診断、合否はCoreの公開契約を正とし、スキルは内部Python APIに依存しない。
`verify`が起動するテストの副作用は実行前に確認する。
結果のJSON表示は保存を意味せず、保存を依頼された`check`・`verify`だけに`--report`を指定する。

本実装はPhase 1の検証対象である。Skill Gate 0〜3の独立認定とリリース認定は別に行う。
公開試作の結果やCoreのGate A〜Cを、スキルの認定へ読み替えない。
