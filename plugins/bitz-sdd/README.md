# bitz-sdd 0.1.0

BitzSkills 2系の仕様計画を支援する日本語スキルの試作版。1系とは別の実装である。
入口は `skills/sdd-plan/SKILL.md`。実装・収束のスキルは未実装で、モデル行動とSkill Gateは未認定。

機能、バグ修正、保守、スパイクの相談を既存仕様に結び付く計画へ整理する。
計画だけの依頼は会話への提案、文書作成も依頼された場合は必要な草案の保存までを担当する。
要求の承認、コード実装、テスト実行、外部公開は計画と区別する。

bitz-core 1.0.0の公開CLI、Linux / macOS、CPython 3.12以上が必要である。
Core実行体は別途導入する。このプラグインはCLI、独自の診断器、状態管理を同梱せず、Core内部APIへ依存しない。
正本はリポジトリのSDDフロー、SPECモデル、EARS-AI、ADR-060。本文と参照はそれらの利用手順である。

配布例のローカル検査:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 tests/skills/test_sdd_plan_examples.py
```

この検査は公開CLIで構文・状態・境界を確認する。モデル行動や例の要求の実証とは別の検査である。
