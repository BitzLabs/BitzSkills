# evals/env-update — マイグレーション機構の合成フィクスチャ検証

ENV-FR-011 / CORE-CON-009 が要求する env-update マイグレーション機構の2挙動を、
plugin-creator `migration-steps.md`「動作確認の指針」の合成フィクスチャ手順に従って
確認した記録。

## 対象と手法

bitz-env の `references/migrations/` は初回出荷時は空（形式変更なし）が正のため、
検証対象は**機構そのもの**（チェーン解決・連続性検査・guard による冪等性・安全側停止）。
宣言的 Markdown ステップをエージェントが解釈実行する挙動を決定的にモデル化した
使い捨てハーネス `verify_migration.py`（本番の実行コードではない）で、スクラッチ領域の
合成フィクスチャに対して以下を確認した。

## 結果（`fixture-run.log` が実出力）

| フィクスチャ | 内容 | 期待 | 結果 |
| --- | --- | --- | --- |
| Fixture 1 | ステップ `0.6.0→0.7.0` と `0.8.0→0.9.0`（`0.7.0→0.8.0` を欠落）で D=0.6.0→T=0.9.0 | チェーン断裂を dry-run で検出し安全側停止、レジストリ書き込み無し | **PASS**（SAFE_STOP・レジストリ不変） |
| Fixture 2 | ステップ `0.6.0→0.7.0`（guard: `migrated_070` 存在）を同一状態へ二重適用 | 1回目 transform 適用、2回目は guard 成立で no-op・状態不変 | **PASS**（stamp 後 D>=T で NO_MIGRATION、適用済み状態への再適用は guard no-op） |

総合: Fixture1=PASS / Fixture2=PASS（EXIT=0）。

## 再実行

```
python3 evals/env-update/verify_migration.py
```

exit code 0 が両フィクスチャ PASS を表す。ハーネスは移行機構の骨子（`resolve_chain` の
連続性検査・`apply_step` の guard→transform→verify 順・stamp を最後に置く擬似トランザクション）を
そのまま反映しており、`references/migration-runbook.md` の手順と一対一で対応する。
