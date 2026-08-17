---
id: SI-FLW-076
raised_by: PR #296 self-review / FLW-REV-020
target: FLW-FR-012 の上限到達時BLOCKED契約と、M2 manifestのunbounded裁定の整合
proposed_change_type: modify
status: accepted
---
- **目的**: `FLW-FR-012` が定める「上限到達時の `BLOCKED` と人間裁定」の契約と、PR #296 が
  導入する M2 remediation manifest の `unbounded`・自動停止なしを整合させる。現在は同一要件の
  検証対象が相反するため、manifest test が green でも要件を満たしたとは判断できない。
- **提案する修正**: 次のどちらを採るか人間が裁定する。(A) M2 remediation に明示的な上限を戻し、
  到達時に停止・裁定要求する。(B) `FLW-REV-018` の是正だけを対象に上限なしとする条件、適用期間、
  M3開始時に再び上限と再校正を要求する条件を `FLW-FR-012` へ追加する。Bを採る場合は既存の
  「上限到達時」条項との優先順位も明記する。
- **対象ファイル**: `.spec/requirements/FLW-FR-012.md`、`.spec/design/FLW-DSN-014.md`、
  `evals/flow-core/m2-eval/record_run.py`、`evals/flow-core/m2-eval/run-manifest-m2-remediation.json`、
  `tests/test_flow_m2_run_manifest.py`、`tests/test_m2_budget_consistency.py`
- **確認観点**: 上限あり・上限なしの各裁定で、記録器の出力、停止条件、裁定参照、M3〜M5予算再校正が
  EARS受入基準から一意に導出できること。上限なしを全milestoneの恒久的な無制限許可として解釈できないこと。
- **影響推定・ロールバック**: 受入基準の変更は要件契約に触れるため、通常フローと人間の approved裁定を
  要する。裁定前は PR #296 のmanifest変更をマージしない。Aを採る場合はmanifest v1相当の停止挙動へ
  戻せる。Bを採る場合もM2限定の例外として隔離できる。
- **依存**: `FLW-REV-020:SYN-001`。強い改ざん耐性をV2対象外とする裁定とは独立。
