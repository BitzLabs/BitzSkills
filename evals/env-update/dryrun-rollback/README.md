# evals/env-update/dryrun-rollback — dry-run の git 管理状態実確認の合成フィクスチャ検証

ENV-FR-013（env-update dry-run の git 管理状態実確認と rollback 手段の正確な提示。
SI-ENV-025 由来）の manual-check を、gitignore されたレジストリを持つ模擬リポジトリ
（本リポジトリ相当）で確認した記録。親ディレクトリの `verify_migration.py` /
`stamp-rescue/verify_rescue.py` と同じ流儀の使い捨てハーネス
`verify_dryrun_rollback.py` で、SKILL.md 手順4.3〜4.4 の実確認ロジックを決定的に
モデル化した（本番の実行コードではない）。

## 結果（`fixture-run.log` が実出力）

| 観点 | 内容 | 期待 | 結果 |
| --- | --- | --- | --- |
| G1 | gitignore されたレジストリ `.claude/bitz-env.local.md` | rollback 手段 = `.bak`（SI-ENV-025 の誤提示「git」が再発しない） | **PASS** |
| G2 | git 管理下の `AGENTS.md` | rollback 手段 = git | **PASS** |
| G3 | 未追跡（ignore 対象外）の `.claude/agents/advisor.md` | rollback 手段 = `.bak` | **PASS** |
| G4 | SKILL.md 手順4・手順5.1・migration-runbook.md のドキュメント検査 | 実確認コマンド・対提示・推測禁止・レジストリ注記・手順4.3 との接続が明文化 | **PASS** |

総合: G1〜G4 すべて PASS（EXIT=0）。

## 再実行

```
python3 evals/env-update/dryrun-rollback/verify_dryrun_rollback.py
```

exit code 0 が全観点 PASS を表す。判定ロジック（`git ls-files --error-unmatch` で追跡判定 →
未追跡は ignore の有無によらず管理外 = `.bak` 必取得）は `skills/env-update/SKILL.md`
手順4.3〜4.4 / 手順5.1 と一対一で対応する。
