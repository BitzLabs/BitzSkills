# Coreスキル本実装のモデル評価準備

## 状態

Phase 0は完了し、`feat/core-skill-japanese` の `94a585ac` までPUSH済み。
Phase 1は進行中。本記録は評価環境の検証であり、モデル評価またはGate 1〜3の認定ではない。

評価環境の確定ref: `c658ef3cebfc005e75fac271a0a10cb0347b3345`。
このrefのcleanな作業ツリーで、以下の検証を実施した。

## 実出力

`PYTHONDONTWRITEBYTECODE=1 python3 evals/skills/core/evaluate.py audit`

```json
{"status":"Passed","version":"core-0.1.0","routingCases":45,"actionCases":22,"errors":[]}
```

試験実行では `TMPDIR=/tmp`、`PYTHONDONTWRITEBYTECODE=1` を指定した。
Core依存が必要な試験では、`PYTHONPATH` にこのリポジトリの `plugins/bitz-core/src` と
既存のruamel.yamlキャッシュ `/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i` を指定した。

| コマンド | 実出力 | 終了コード |
|---|---|---|
| `python3 tests/skills/test_core_skill_eval.py` | `Ran 7 tests in 1.394s` / `OK` | 0 |
| `python3 tests/skills/test_skill_eval.py` | `Ran 27 tests in 5.119s` / `OK` | 0 |
| `python3 tests/skills/test_core_skill_commands.py` | `Ran 1 test in 1.094s` / `OK` | 0 |

独立コンテキスト `core_eval_review` は、評価器の範囲拡大・終了コード不整合・
偽ツール応答・baseline欠測・危険登録の負対照を再検証し、指摘した重大な未解消事項が
ないことを報告した。上表の検証は作業者が別途再実行した結果である。

## 残作業

- スキルあり／なしの同条件モデル実測（判断45件、実操作22件、各2反復）。
- モデル軌跡とホスト記録の照合、結果説明の独立内容検分。
- 試作ゲートの判定と記録。保持ケースと実地パイロットは別途必要。

Codex CLIの接続確認は `Read-only file system` で起動に失敗した。
標準内部状態を作成する `/home/hide/.codex` への書込みについて、ユーザーに明示承認を
依頼済みであり、回答待ちである。AGENTS.mdのリポジトリ外書込み規則に従い、
モデル実測は開始していない。評価器の機械採点だけではGateを認定しない。
