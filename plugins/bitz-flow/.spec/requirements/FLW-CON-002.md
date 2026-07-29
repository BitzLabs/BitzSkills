---
id: FLW-CON-002
version: 1.0
status: draft
domain: governance
priority: high
origin: FLW-DSN-012
verification_method: unit-test
derived_from:
supersedes: FLW-FR-001
superseded_by:
confidence: high
---

### FLW-CON-002 操作安全境界と外部承認

- **説明**: v1の後片付け不変条件を継承し、全operationの副作用上限と承認責任を固定する。
- **受入基準 (EARS)**:
  - WHEN operationを登録する THEN bitz-flowはclass、target、preconditions、effects、approval、postconditions、retry、concurrency key、partial、evidenceをOperation Contractへ要求すること SHALL
  - WHEN operationがplanにない副作用を要求する THEN bitz-flowはapplyを`BLOCKED`にすること SHALL
  - WHEN destructive operationをapplyする THEN SKILLまたはオーケストレーション層は可視の人間応答前にCLI applyを呼び出さないこと SHALL
  - WHEN `--approval-ref`を受け取る THEN bitz-flowは参照の存在だけでapply可否を変更しないこと SHALL
  - WHEN cleanup前提を検査する THEN bitz-flowはPR state、head branch、head SHA、default到達性を再照会すること SHALL
  - WHEN remote branch削除を計画する THEN bitz-flowはmerge、local cleanup、release操作へ自動連結しないこと SHALL
  - WHEN command policyを検査する THEN bitz-flowは`git reset --hard`、force push、`git clean -f`、`rm -rf`、`sudo`の実装・提案0件を記録すること SHALL
  - WHEN raw stdout、raw stderr、credentialを受け取る THEN bitz-flowは公開resultと例外messageへ転記しないこと SHALL
- **検証手段**: operation schema欠落、effects逸脱、人間応答前apply、approval-ref自己申告、禁止command、raw出力漏洩をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-FR-001のv2後継安全境界としてdraft起票
