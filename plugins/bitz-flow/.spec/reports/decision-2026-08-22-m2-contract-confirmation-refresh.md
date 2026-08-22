# 裁定記録 — M2契約核変更後のconfirmation証跡更新

- **日付**: 2026-08-22
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-083`、`FLW-TSK-106`、M2 qualification/confirmation証跡
- **裁定原文**: 「OK」
- **提示済み提案**: 新しいcontract/approval核をcompatibility keyへ追加し、既存の
  `evals/flow-core/m2-eval/`配下のqualification・confirmation証跡を再実走結果で上書きする。
- **記録者**: codex（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

1. `SI-FLW-083`をacceptedとする。
2. `FLW-TSK-106`の変更境界へconfirmation runner、qualification/confirmation manifest、
   attempt台帳、raw log、対応testを追加する。
3. `COMPATIBILITY_INPUTS`へ新しいcontract/approval module、schema、testを追加する。
4. 現在のcompatibility keyでqualificationと3platform confirmationを実走する。
5. AGENTS.mdが事前確認を要求する既存`evals/`成果物の上書きを、本裁定により明示承認する。

## 受入条件

- active manifestが現在のcompatibility keyと一致し、`dry_run: false`、3platform PASSである。
- 全platformのtest ID集合とruntime check数が一致し、hazard/residualが0件である。
- qualification TTL、attempt chain、raw log canary/redaction検査がPASSする。
