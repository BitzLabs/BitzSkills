---
id: QLT-DSC-000
title: "bitz-quality レビュー基盤 ディスカバリー作業台帳"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# bitz-quality レビュー基盤 ディスカバリー作業台帳

## 現在地

- 起点: `SI-CORE-040` → `SI-QLT-001`
- 現行: quality-reviewは実装先行で、論理Reviewer、platform adapter、出力schemaの境界が未確定
- 将来候補: bitz-sddの`sdd-review`汎用責務を互換性を保って段階移管
- 現在のGate: Discovery Gate Go（2026-08-14）済み、Design Gate準備中

## Open Questions

1. サブエージェントを配布物として同梱するplatformと、prompt/referenceで代替するplatformの境界は何か。
2. LLM結果の非決定性に対して、どのfieldを決定的oracleで検査するか。
3. review profileの所有者をquality、プロジェクト、SDDのどこに置くか。
4. `sdd-review`をdeprecatedにできる最小parity条件は何か。
