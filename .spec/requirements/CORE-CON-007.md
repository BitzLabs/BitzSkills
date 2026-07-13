---
id: CORE-CON-007
version: 1.0
status: approved
domain: governance
priority: medium
origin: SI-CORE-021
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-007 委譲の損益分岐と過剰委譲防止

- **説明**: 委譲は無条件に善ではない。往復コストが節約を上回る**小さな単発タスク**は委譲せず
  司令塔が直接実行する、という損益分岐を委譲ゲートに明記し、過剰委譲を誘発しないためのガードとする。
- **受入基準 (EARS)**:
  - THE 委譲ゲートは委譲の損益分岐（往復コスト > 節約となる小さな単発タスクは委譲しない）を明記すること SHALL
  - IF タスクが1ファイルの軽微な編集など損益分岐を下回る規模 THEN 委譲せず司令塔が直接実行すること SHALL
- **検証手段**: delegation-routing / sdd-implement の inspection。損益分岐の明記と、
  小さな単発タスクを自己実行に振り分ける基準の記述を確認する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
