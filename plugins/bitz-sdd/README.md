# bitz-sdd 0.2.0

BitzSkills 2系の仕様計画と実装を支援する日本語スキルの試作版。1系とは別の実装である。
計画の入口は `skills/sdd-plan/SKILL.md`、実装の入口は `skills/sdd-implement/SKILL.md`。
収束のスキルは未実装で、モデル行動とSkill Gateは未認定。

機能、バグ修正、保守、スパイクの相談を既存仕様に結び付く計画へ整理する。
計画だけの依頼は会話への提案、文書作成も依頼された場合は必要な草案の保存までを担当する。
要求の承認、コード実装、テスト実行、外部公開は計画と区別する。

実装は承認済みの起点から、完全なcontext、実装前check、書込み直前のdigest再照合を経て進める。
変更後のcheckと安全なverifyの実結果を人手レビューへ渡す。人手レビュー未実施は不足として残し、
Core通過をTASK完了や出荷許可に置き換えない。

bitz-core 1.0.0の公開CLI、Linux / macOS、CPython 3.12以上が必要である。
Core実行体は別途導入する。このプラグインはCLI、独自の診断器、状態管理を同梱せず、Core内部APIへ依存しない。
正本はリポジトリのSDDフロー、SPECモデル、EARS-AI、ADR-060。本文と参照はそれらの利用手順である。

配布例のローカル検査:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 tests/skills/test_sdd_plan_examples.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 tests/skills/test_sdd_implement_connection.py
```

計画の検査は公開CLIで構文・状態・境界を確認する。接続の検査は合成workspace内のPythonテストも実行し、
静的検査と実テスト、contextと差分、不足する人手レビューを区別する。
モデル行動や製品要求の実証・認定とは別の検査である。
