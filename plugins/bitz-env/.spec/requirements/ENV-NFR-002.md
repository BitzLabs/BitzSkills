---
id: ENV-NFR-002
version: 1.0
status: implementing
domain: guardrail
priority: low
origin: SI-ENV-004（REV-001 business BIZ-201）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: medium
---

### ENV-NFR-002 rules 注入サイズの節度

- **説明**: SessionStart フックは rules/*.md をコンテキストへ注入するため、rules が
  肥大するとセッション毎のコンテキストを圧迫する。注入は必要最小限に保つ。
- **受入基準 (EARS)**:
  - WHERE rules/*.md を編集・追加する箇所 THE システムは注入対象をガードレール本文に 限定し、肥大化を避ける SHALL
  - IF rules 合計が過大になった場合 THEN 要約・分割の方針を検討する SHALL
- **検証手段**: rules/ の内容レビュー（manual-check。注入サイズの目視確認）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-ENV-004 accepted による）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
