# evals/env-update/stamp-rescue — stamp 後付け救済フローの合成フィクスチャ検証

ENV-FR-012（bitz-env-version 未記録環境の stamp 後付け救済）の manual-check 4観点を、
ENV-DSN-002 の設計（保守的推定 D̂ と guard 冪等性）に従って確認した記録。
親ディレクトリの `verify_migration.py`（ENV-FR-011 検証）と同じ流儀の使い捨てハーネス
`verify_rescue.py` で、env-update SKILL.md 手順 1b と env-doctor 診断項目4の挙動を
決定的にモデル化した（本番の実行コードではない）。

## 結果（`fixture-run.log` が実出力）

| フィクスチャ | 内容 | 期待 | 結果 |
| --- | --- | --- | --- |
| R1 | 未記録レジストリを env-doctor で診断 | WARN + 救済手順（env-update 手順 1b）提示、入力不変（読み取り専用） | **PASS** |
| R2 | 救済承認 → D̂=0.7.0 stamp → step 適用 → T=0.8.0 stamp。再実行・ステップ不在・途中失敗の3変種も確認 | 正常系へ収束（再実行は D>=T で更新不要、途中失敗後も D̂ が残り救済フローを経ず収束） | **PASS** |
| R3 | レジストリ自体が不在 | 救済対象外・env-init の実行を案内して安全側停止 | **PASS** |
| R4 | 救済フローをユーザーが非承認 | 一切書き込まずレジストリ不変のまま安全側停止 | **PASS** |

総合: R1〜R4 すべて PASS（EXIT=0）。

## 再実行

```
python3 evals/env-update/stamp-rescue/verify_rescue.py
```

exit code 0 が全観点 PASS を表す。ハーネスは救済フローの骨子（保守的推定
`estimate_d`（最古ステップの `from`、不在時は stamp 機構導入版 0.7.0）・承認後の適用の
最初に D̂ stamp・guard→transform→verify・完了時 T stamp）をそのまま反映しており、
`skills/env-update/SKILL.md` 手順 1b / 5 と一対一で対応する。
